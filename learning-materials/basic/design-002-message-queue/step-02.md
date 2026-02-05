# Step 02: Handling Failures and Duplication

---

## Question 3: How to Handle Failures?

**Retry strategy:**
```python
# Exponential backoff
retry_delays = [1s, 2s, 4s, 8s, 16s, 32s]  # Max 6 retries
max_retry_duration = sum(retry_delays)  # ~63 seconds

# After max retries: Dead Letter Queue
dlq_exchange = 'posts.dlq'
```

**RabbitMQ configuration:**
```python
# Queue with TTL and DLQ
args = {
    'x-message-ttl': 60000,  # 60 second max processing time
    'x-dead-letter-exchange': 'posts.dlq',
    'x-max-retry-count': 6
}

channel.queue_declare(
    queue='timeline.worker',
    arguments=args
)
```

**DLQ processing:**
```python
# Alert team
# Investigate failure
# Manual replay or discard
```

---

## Question 4: Preventing Duplication

**Problem:** At-least-once delivery means messages may be duplicated.

**Solution 1: Idempotency key**
```python
def process_post_event(event):
    event_id = event['event_id']

    # Check if already processed
    if redis.exists(f"processed:{event_id}"):
        return  # Skip duplicate

    # Process event
    add_to_timelines(event['data'])

    # Mark as processed (with TTL)
    redis.setex(f"processed:{event_id}", 3600, '1')
```

**Solution 2: Database constraints**
```sql
-- Timeline table with unique constraint
CREATE TABLE timeline_entries (
    user_id BIGINT NOT NULL,
    post_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (user_id, post_id)  -- Prevents duplicates
);
```

**Solution 3: Transactional outbox**
```sql
BEGIN;
-- 1. Save post
INSERT INTO posts ... VALUES (...);

-- 2. Save outbox event
INSERT INTO outbox (event_id, event_type, payload)
VALUES ('evt_123abc', 'post.created', '{"post_id": 789, ...}');
COMMIT;

-- Separate worker polls outbox and publishes to queue
```

---

## Question 5: Queue Backup (Backpressure)

**Problem:** At peak, 10M messages queued. Workers can't keep up.

**Solutions:**

**1. Add more workers (horizontal scaling)**
```python
# Auto-scaling based on queue depth
queue_depth = get_queue_depth('timeline.worker')
desired_workers = max(1, queue_depth // 10000)
scale_workers(desired_workers)
```

**2. Priority queues**
```python
# High priority: Posts from verified users
queue_high = 'timeline.vip'

# Low priority: Posts from new users
queue_low = 'timeline.normal'
```

**3. Shed load (graceful degradation)**
```python
if queue_depth > CRITICAL_THRESHOLD:
    # Skip analytics events
    # Defer non-critical notifications
    # Throttle non-VIP users
```

---

## Architecture Diagram

```
┌─────────────┐
│   Post      │
│  Service    │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  RabbitMQ       │
│  fanout exchange│
└────┬────┬────┬──┘
     │    │    │
     ▼    ▼    ▼
┌─────────┐ ┌─────────┐ ┌──────────┐
│ Timeline│ │  Push   │ │Analytics │
│ Workers │ │ Workers │ │ Workers  │
└─────────┘ └─────────┘ └──────────┘
     │           │           │
     ▼           ▼           ▼
┌─────────┐ ┌─────────┐ ┌──────────┐
│Timeline │ │  Push   │ │Analytics │
│  Store  │ │ Service │ │  Store   │
└─────────┘ └─────────┘ └──────────┘
```

---

## Summary

| Concern | Solution |
|---------|----------|
| Technology choice | RabbitMQ (mature, fanout support) |
| Message structure | One message per post, workers fanout |
| Failure handling | Retry with backoff + DLQ |
| Duplication | Idempotency keys + database constraints |
| Queue backup | Auto-scale + priority queues + shedding |

---

**Now read `solution.md` for the complete design.**

---

## Quick Check

Before moving on, make sure you understand:

1. What's a Dead Letter Queue (DLQ)? (Destination for failed messages after retries)
2. How do you handle duplicate messages? (Idempotency keys, database constraints, outbox pattern)
3. What's exponential backoff for retries? (1s, 2s, 4s, 8s... prevent thundering herd)
4. What's the transactional outbox pattern? (Write event + data in same transaction, separate worker publishes)
5. How do you handle queue backup? (Auto-scale workers, priority queues, shed load)

