# Step 01: Choosing the Queue Technology

---

## Question 1: What Queue Technology?

**Considerations:**
- Order required? (Posts should be delivered in order)
- Persistence required? (Can't lose notifications)
- Fanout? (One post → many followers)
- Consumer lag tolerance? (30 seconds for timeline)

**Options:**

| Technology | Pros | Cons | Best For |
|------------|------|------|----------|
| **RabbitMQ** | Mature, routing, ACKs | Operational overhead | Complex routing |
| **Kafka** | High throughput, replay | Complex, overkill for small scale | Event streaming |
| **SQS** | Managed, simple | No ordering, 256KB limit | Simple tasks |
| **Redis** | Fast, simple | Limited persistence | Caches, temporary |

**Recommendation: RabbitMQ**

```python
# RabbitMQ fanout exchange
exchange = 'posts.fanout'
queue_timeline = 'timeline.worker'
queue_push = 'push.worker'
queue_analytics = 'analytics.worker'

# Bind all queues to fanout exchange
# One message → all queues receive copy
```

---

## Question 2: How to Structure Messages?

**Two approaches:**

**Approach A: One message per recipient**
```
100K posts × 1000 followers = 100M messages/day
```

```python
# Bad: Too many messages
for follower in post.author.followers:
    queue.publish({
        'type': 'new_post',
        'post_id': post.id,
        'recipient': follower.id
    })
```

**Approach B: One message per post (fanout at worker)**
```
100K messages/day, workers handle fanout
```

```python
# Good: One message, workers fanout
queue.publish({
    'type': 'new_post',
    'post_id': post.id,
    'author_id': post.author.id,
    'created_at': post.created_at
})

# Timeline worker:
# 1. Receive message
# 2. Fetch followers
# 3. Add to each follower's timeline
```

**Approach B is better:**
- Fewer messages = less overhead
- Workers can batch operations
- Single message has all needed context

---

## Question 3: Message Format

```json
{
  "event_id": "evt_123abc",           // Unique identifier
  "event_type": "post.created",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "post_id": 789,
    "author_id": 123,
    "content": "Hello world!",
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

**Key fields:**
- `event_id`: Idempotency key (prevent duplicate processing)
- `event_type`: Routing key for different handlers
- `timestamp`: Order and retry logic

---

**Still thinking? Read `step-02.md`**

---

## Quick Check

Before moving on, make sure you understand:

1. Why is RabbitMQ recommended over Kafka? (Mature, routing features, not overkill for this scale)
2. Why one message per post instead of per follower? (100K vs 100M messages, workers fanout)
3. What's a fanout exchange? (One message delivered to all bound queues)
4. What key fields does a message need? (event_id for idempotency, event_type for routing, timestamp)
5. How do you structure message data? (Envelope with metadata + data payload)

