---
name: design-002-message-queue
description: Message Queue Design
difficulty: Basic
category: System Design
level: Mid-level
---
# Design 002: Message Queue Design

---

## The Situation

You're designing the notification system for Connectify (from Design 001).

When a user posts:
1. Their followers need to see the post in their timeline
2. They might get push notifications
3. Analytics events need to be sent

**Scale**: 100K posts per day peak, users have 1000 average followers.

**Problem**: Delivering 100M notifications per day (100K posts × 1000 followers) synchronously is impossible.

---

## Requirements

> "When a user posts:
> - Add to followers' timelines (eventual consistency OK)
> - Send push notification to users who enabled them
> - Track delivery (failed notifications should be retried)
> - Order doesn't matter (fanout)"
>
> "Latency: Timeline update should be visible within 30 seconds"
> "Push notification: within 5 seconds"

---

## Jargon

| Term | Definition |
|------|------------|
| **Fanout** | One message expanding to multiple recipients (one post → many followers) |
| **Eventual consistency** | System will become consistent eventually, not immediately |
| **Message queue** | Async communication buffer; producers send messages, consumers process them |
| **At-least-once delivery** | Message guaranteed to be delivered, possibly multiple times |
| **At-most-once delivery** | Message guaranteed to be delivered at most once (may be dropped) |
| **Exactly-once delivery** | Holy grail; delivered exactly once (requires idempotency) |
| **Dead letter queue (DLQ)** | Queue for messages that repeatedly failed processing |
| **Backpressure** | Signal to slow down when consumers can't keep up |
| **Consumer lag** | How far behind consumers are (messages in queue, oldest message age) |

---

## Your Task

1. **What queue technology would you use?** (RabbitMQ, Kafka, SQS, Redis?)

2. **How do you structure the messages?** (One message per recipient? One message per post?)

3. **How do you handle failures?** (Retries, DLQ, ordering?)

4. **How do you prevent duplication?** (Idempotency keys?)

5. **What happens when queue backs up?** (At peak, 10M messages queued)

---

## Architecture Considerations

```
Producer (Post Service) → Queue → Consumers (Timeline Service)
                                         → Consumers (Push Service)
                                         → Consumers (Analytics)
```

Should you use:
- One queue per consumer type?
- One queue with routing?
- Different queue for high vs low priority?

---

**When you have a design, read `solution.md`**
