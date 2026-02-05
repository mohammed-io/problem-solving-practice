# Step 2: Implementing Backpressure

---

## Solution 1: Bounded Concurrency (Recap)

```go
// RIGHT: Limit concurrent processing with semaphore
func (c *BoundedConsumer) Run(ctx context.Context) error {
    sem := make(chan struct{}, 100) // Max 100 concurrent

    for {
        select {
        case <-ctx.Done():
            return ctx.Err()
        default:
        }

        records := c.consumer.Poll(100 * time.Millisecond)

        for _, record := range records {
            sem <- struct{}{} // Block if at capacity
            go func(r ConsumerRecord) {
                defer func() { <-sem }()
                c.Process(r)
            }(record)
        }
    }
}
```

**Now:** Consumer pauses when 100 tasks in-flight. Kafka build-up signals producer.

---

## Solution 2: Reactive Streams in Go

```go
package reactive

import (
    "context"
    "sync"
)

// Subscriber receives values with backpressure
type Subscriber interface {
    OnNext(value interface{})
    OnError(err error)
    OnComplete()
}

// Subscription allows controlling flow
type Subscription interface {
    Request(n int)  // Request n more values
    Cancel()        // Cancel subscription
}

// Publisher produces values
type Publisher interface {
    Subscribe(sub Subscriber) Subscription
}

// FlowControl implements reactive backpressure
type FlowControl struct {
    buffer     chan interface{}
    demand     chan int
    cancel     chan struct{}
    once       sync.Once
}

func NewFlowControl(bufferSize int) *FlowControl {
    return &FlowControl{
        buffer: make(chan interface{}, bufferSize),
        demand: make(chan int, 1),
        cancel: make(chan struct{}),
    }
}

func (f *FlowControl) Subscribe(sub Subscriber) Subscription {
    fc := &flowControlSubscription{
        fc:   f,
        sub:  sub,
        done: make(chan struct{}),
    }

    go fc.run()

    return fc
}

type flowControlSubscription struct {
    fc      *FlowControl
    sub     Subscriber
    demand  int
    mu      sync.Mutex
    done    chan struct{}
}

func (s *flowControlSubscription) Request(n int) {
    s.mu.Lock()
    s.demand += n
    s.mu.Unlock()

    select {
    case s.fc.demand <- s.demand:
    case <-s.done:
    case <-s.fc.cancel:
    }
}

func (s *flowControlSubscription) Cancel() {
    close(s.fc.cancel)
}

func (s *flowControlSubscription) run() {
    defer close(s.done)

    for {
        select {
        case value, ok := <-s.fc.buffer:
            if !ok {
                s.sub.OnComplete()
                return
            }
            s.sub.OnNext(value)

            s.mu.Lock()
            s.demand--
            s.mu.Unlock()

        case <-s.fc.cancel:
            return
        }
    }
}

// Example: Consumer with backpressure
type BackpressureConsumer struct {
    publisher  Publisher
    batchSize  int
}

func NewBackpressureConsumer(publisher Publisher) *BackpressureConsumer {
    return &BackpressureConsumer{
        publisher: publisher,
        batchSize: 10, // Process 10 at a time
    }
}

func (c *BackpressureConsumer) Run(ctx context.Context) {
    sub := c.publisher.Subscribe(&consumerSubscriber{
        batchSize: c.batchSize,
        ctx:       ctx,
    })

    // Initial request
    sub.Request(c.batchSize)

    <-ctx.Done()
    sub.Cancel()
}

type consumerSubscriber struct {
    batchSize int
    processed int
    sub       Subscription
    ctx       context.Context
}

func (s *consumerSubscriber) OnNext(value interface{}) {
    // Process value
    processRecord(value.(ConsumerRecord))

    s.processed++
    if s.processed >= s.batchSize {
        // Request more
        s.sub.Request(s.batchSize)
        s.processed = 0
    }
}

func (s *consumerSubscriber) OnError(err error) {
    log.Printf("Consumer error: %v", err)
}

func (s *consumerSubscriber) OnComplete() {
    log.Println("Consumer complete")
}

func processRecord(r ConsumerRecord) {
    // Process record
}
```

**Reactive streams:** Downstream signals upstream how many items it can handle.

---

## Solution 3: Producer Throttling

```go
package producer

import (
    "context"
    "time"
)

type TokenBucket struct {
    capacity int64
    tokens   int64
    rate     int64         // Tokens per second
    lastRefill time.Time
    mu       sync.Mutex
}

func NewTokenBucket(capacity, rate int64) *TokenBucket {
    return &TokenBucket{
        capacity:   capacity,
        tokens:     capacity,
        rate:       rate,
        lastRefill: time.Now(),
    }
}

func (tb *TokenBucket) TryConsume(n int64) bool {
    tb.mu.Lock()
    defer tb.mu.Unlock()

    // Refill tokens based on time passed
    now := time.Now()
    elapsed := now.Sub(tb.lastRefill).Seconds()
    tb.tokens += int64(elapsed * float64(tb.rate))
    if tb.tokens > tb.capacity {
        tb.tokens = tb.capacity
    }
    tb.lastRefill = now

    // Check if we have enough tokens
    if tb.tokens >= n {
        tb.tokens -= n
        return true
    }
    return false
}

type Producer struct {
    kafka      *KafkaProducer
    bucket     *TokenBucket
    consumerLag ConsumerLagChecker
}

func NewProducer(kafka *KafkaProducer, maxRate int64) *Producer {
    return &Producer{
        kafka:  kafka,
        bucket: NewTokenBucket(maxRate, maxRate), // capacity = rate
    }
}

func (p *Producer) ProduceWithBackpressure(ctx context.Context, msg Message) error {
    // Check consumer lag
    lag, err := p.consumerLag.GetLag()
    if err != nil {
        return err
    }

    if lag > 100000 {
        return errors.New("consumer lag too high, throttling")
    }

    // Rate limit with token bucket
    if !p.bucket.TryConsume(1) {
        return errors.New("rate limit exceeded")
    }

    return p.kafka.Produce(msg)
}

// ConsumerLagChecker checks consumer lag
type ConsumerLagChecker interface {
    GetLag() (int64, error)
}
```

---

## Solution 4: Small Buffers (Anti-Pattern Fix)

```go
// WRONG: Large buffer = delayed backpressure
largeBuffer := make(chan Message, 10000)

// RIGHT: Small buffer = immediate feedback
smallBuffer := make(chan Message, 10) // Blocks producer quickly
```

**Rule of thumb:** Buffer size should be proportional to your processing capacity, not arbitrary large numbers.

---

## Summary: Backpressure Strategies

| Strategy | Mechanism | Pros | Cons |
|----------|-----------|------|------|
| Bounded Concurrency | Semaphore limits | Simple, effective | Fixed capacity |
| Reactive Streams | Demand signaling | Dynamic, flexible | Complex to implement |
| Producer Throttling | Rate limiting | Protects downstream | Requires lag monitoring |
| Small Buffers | Channel blocking | Immediate feedback | Requires tuning |

---

## Quick Check

Before moving on, make sure you understand:

1. How does bounded concurrency provide backpressure? (Semaphore blocks when capacity reached)
2. What is reactive streaming? (Downstream signals demand to upstream)
3. What is a token bucket? (Rate limiting mechanism with refill)
4. Why are small buffers better for backpressure? (Immediate feedback to producer)
5. What's consumer lag? (Messages produced but not yet consumed)

---

**Continue to `solution.md`**
