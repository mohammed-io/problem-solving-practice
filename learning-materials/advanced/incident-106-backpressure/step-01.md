# Step 1: Understanding the Mismatch

---

## The Flow

```
Producer → [Channel: 10000 buffer] → Kafka → Consumer
            ↑ Never blocks                 ↑ Polls 1000
                                            ↓
                                    [Async Processing]
                                            ↓ (returns immediately)
                                    Loop: Poll again!
```

**Problem:** Consumer polls 1000 messages, kicks off async processing, immediately polls again!

Async processing doesn't finish before next poll. In-flight messages accumulate.

---

## The Buffer Bloat

```go
// Producer side - large buffer
ch := make(chan Message, 10000)

// This allows 10000 messages to queue before blocking
// Producer never knows consumer is slow!

// By the time channel is full, consumer already has:
// - 10000 in channel
// - 10000 in Kafka
// - 50000 in async processing
// = 70000 in-flight messages!
```

**Large buffers = delayed feedback.** By the time producer blocks, system is already overloaded.

---

## Consumer Without Backpressure

```go
// WRONG: No backpressure awareness
func (c *Consumer) Run() {
    for {
        // Poll always returns up to max.poll.records (1000)
        records := c.Poll(100 * time.Millisecond)

        for _, record := range records {
            // Launch async processing - returns immediately!
            go func(r ConsumerRecord) {
                c.Process(r) // Slow processing
            }(record)
        }
        // Loop continues, another poll!
        // No waiting for processing to complete!
    }
}
```

**The problem:** `go func() { ... }()` returns immediately. No signal to slow down polling.

---

## Better Consumer: Bounded Goroutines

```go
package backpressure

import (
    "context"
    "sync"
    "time"
)

type BoundedConsumer struct {
    consumer    *KafkaConsumer
    semaphore   chan struct{} // Limits concurrent goroutines
    wg          sync.WaitGroup
}

func NewBoundedConsumer(maxConcurrent int) *BoundedConsumer {
    return &BoundedConsumer{
        consumer:  NewKafkaConsumer(),
        semaphore: make(chan struct{}, maxConcurrent), // Backpressure!
    }
}

func (c *BoundedConsumer) Run(ctx context.Context) error {
    for {
        select {
        case <-ctx.Done():
            c.wg.Wait() // Wait for all in-flight processing
            return ctx.Err()
        default:
        }

        records := c.consumer.Poll(100 * time.Millisecond)
        if len(records) == 0 {
            continue
        }

        for _, record := range records {
            // Block if at capacity - BACKPRESSURE!
            c.semaphore <- struct{}{}

            c.wg.Add(1)
            go func(r ConsumerRecord) {
                defer c.wg.Done()
                defer func() { <-c.semaphore }() // Release when done

                c.Process(r)
            }(record)
        }

        // Now: If 100 goroutines processing, poll blocks on semaphore
        // Kafka builds up → producer detects lag → slows down
    }
}

func (c *BoundedConsumer) Process(record ConsumerRecord) error {
    // Simulate slow processing
    time.Sleep(100 * time.Millisecond)
    return nil
}
```

**Now:** Consumer pauses when 100 tasks in-flight. Kafka build-up signals producer.

---

## Quick Check

Before moving on, make sure you understand:

1. What is backpressure? (Signal from consumer to producer to slow down)
2. Why do large buffers cause problems? (Delayed feedback, overload before producer knows)
3. What happens when async processing returns immediately? (No signal to slow down)
4. How does a semaphore provide backpressure? (Blocks when capacity reached)
5. Why is feedback important in streaming systems? (Prevents unbounded memory growth)

---

**Continue to `step-02.md`**
