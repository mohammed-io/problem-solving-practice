# Solution: Backpressure Mismatch - End-to-End Flow Control

---

## Root Cause

**Three failures:**
1. Producer: Large buffer = no feedback on consumer capacity
2. Consumer: Async processing without concurrency limits
3. No end-to-end flow control

---

## Complete Solution

### Consumer: Bounded Concurrency

```java
public class BackpressuredConsumer {
    private final KafkaConsumer<String, String> consumer;
    private final ExecutorService executor;
    private final Semaphore semaphore;

    public BackpressuredConsumer(int maxConcurrency) {
        this.executor = Executors.newFixedThreadPool(maxConcurrency);
        this.semaphore = new Semaphore(maxConcurrency);
    }

    public void run() {
        while (true) {
            ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));

            for (ConsumerRecord<String, String> record : records) {
                // Block if we're at capacity
                semaphore.acquireUninterruptibly();

                executor.submit(() -> {
                    try {
                        process(record);
                    } finally {
                        semaphore.release();  // Always release
                    }
                });
            }

            // Only poll for more if we have capacity
            semaphore.acquireUninterruptibly(records.count());
            consumer.commitSync();
            semaphore.release(records.count());
        }
    }
}
```

### Producer: Consumer-Lag Aware

```go
type Producer struct {
    kafka   *kafka.Writer
    client  *kafka.Client
    topic   string
}

func (p *Producer) ProduceWithBackpressure(ctx context.Context, key, value string) error {
    // Check consumer lag
    lag, err := p.getConsumerLag(p.topic)
    if err != nil {
        return err
    }

    if lag > 100000 {
        return errors.New("consumer lag too high, throttling")
    }

    // Produce message
    return p.kafka.WriteMessages(ctx, kafka.Message{
        Key:   []byte(key),
        Value: []byte(value),
    })
}

func (p *Producer) getConsumerLag(topic string) (int64, error) {
    // Get consumer group lag
    partitions, err := p.client.GetConsumerLag(topic, "my-group")
    if err != nil {
        return 0, err
    }

    var totalLag int64
    for _, partition := range partitions {
        totalLag += partition.Lag
    }

    return totalLag, nil
}
```

### Reactive Streams Approach

```java
// Using Project Reactor
public class ReactiveConsumer {
    public Flux<ProcessedResult> consumeWithBackpressure() {
        return Flux.create(emitter -> {
            KafkaConsumer<String, String> consumer = newConsumer();
            consumer.subscribe(Collections.singletonList("topic"));

            while (!emitter.isCancelled()) {
                ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));
                for (ConsumerRecord<String, String> record : records) {
                    emitter.next(record);
                }
            }
        })
        .flatMap(record ->
            Mono.fromCallable(() -> process(record))
                .subscribeOn(Schedulers.parallel())
                ,  // Concurrency limit
            100  // Max 100 in-flight
        )
        .doOnNext(result -> consumer.commitSync())
        .doOnError(error -> log.error("Error", error));
    }
}
```

---

## Systemic Prevention

### Monitoring

```promql
# Consumer lag
- alert: HighConsumerLag
  expr: |
    kafka_consumer_lag > 100000
  labels:
    severity: warning

# Producer throttle rate
- alert: ProducerThrottled
  expr: |
    rate(producer_throttled_total[5m]) > 100
  labels:
    severity: info

# In-flight messages growing
- alert: InFlightGrowing
  expr: |
    delta(consumer_in_flight[5m]) > 0
  labels:
    severity: warning
```

### Circuit Breaker for Producer

```go
type Producer struct {
    circuitBreaker *circuit.Breaker
}

func (p *Producer) Produce(key, value string) error {
    if p.circuitBreaker.State() == circuit.Open {
        return errors.New("circuit open, producer throttled")
    }

    lag, _ := p.getConsumerLag()
    if lag > THRESHOLD {
        p.circuitBreaker.RecordFailure()
        return errors.New("lag too high")
    }

    err := p.kafka.WriteMessages(...)
    if err == nil {
        p.circuitBreaker.RecordSuccess()
    }

    return err
}
```

---

## Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| **Bounded semaphore** | Simple, effective | Lower throughput |
| **Reactive streams** | Built-in backpressure | Learning curve, framework lock-in |
| **Producer throttling** | Prevents overload at source | Producer needs lag visibility |
| **Load shedding** | Protects system | Drops requests |

**Recommendation:** Bounded concurrency at consumer + producer lag monitoring.

---

**Next Problem:** `advanced/incident-107-quorum-drift/`
