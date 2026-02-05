# Design 002: Solution - Message Queue for Fanout

---

## The Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Post Service                              │
│  ┌───────────────────────────────────────────────────────────────┐ │
││  1. Save post to DB                                              │ │
││  2. Publish "NewPost" event to Kafka                             │ │
│└───────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Kafka (NewPost Topic)                            │
│  - Partition key: post_id (ensures ordering per post)              │
│  - Retention: 7 days                                             │
│  - Replication: 3                                                 │
└─────────────┬───────────────────────────────────────────────────────┘
              │
      ┌───────┴────────┬────────────────┐
      ▼                ▼                ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ Timeline    │  │ Push        │  │ Analytics  │
│ Consumer    │  │ Consumer    │  │ Consumer    │
│ Group       │  │ Group       │  │ Group       │
│             │  │             │  │             │
│ Process:    │  │ Process:    │  │ Process:    │
│ Add to      │  │ Send via    │  │ Increment   │
│ follower    │  │ FCM/APNS    │  │ counters    │
│ timelines   │  │             │  │             │
└─────────────┘  └─────────────┘  └─────────────┘
```

---

## Why Kafka?

| Queue Type | Good For | Bad For |
|------------|----------|---------|
| **Kafka** | High throughput, replay, multiple consumer groups | Low latency (<10ms) |
| **RabbitMQ** | Complex routing, low latency | Very high throughput |
| **SQS** | Serverless, simple | Fanout to many consumers |
| **Redis** | Simple pub/sub | Durability, replay |

**Kafka chosen for:**
- High throughput (100M messages/day)
- Multiple independent consumer groups
- Replay (new consumer can start from beginning)
- Durability (messages persisted to disk)

---

## Message Structure

```json
{
  "event_type": "new_post",
  "event_id": "evt_20241127_abc123",
  "timestamp": "2024-11-27T10:15:30Z",
  "post": {
    "id": "post_12345",
    "author_id": "user_67890",
    "created_at": "2024-11-27T10:15:30Z",
    "content": "Hello world!"
  }
}
```

**Not one message per recipient** - that would create 100K messages × 1000 followers = 100M messages!

Instead: **One message per post**, each consumer group handles fanout.

---

## Consumer Group: Timeline

```javascript
async function processNewPost(message) {
  const { post } = message;

  // Get followers (from cache or DB)
  const followerIds = await getFollowers(post.author_id);

  // Batch process followers
  for (const batch of chunk(followerIds, 1000)) {
    // Add to timelines
    await pg.query(`
      INSERT INTO timeline (user_id, post_id, created_at)
      VALUES ${batch.map(id => `(${id}, ${post.id}, '${post.created_at}')`).join(',')}
      ON CONFLICT DO NOTHING  -- Idempotent!
    `);
  }
}
```

**Timeline table** (denormalized for fast reads):

```sql
CREATE TABLE timeline (
  user_id BIGINT NOT NULL,
  post_id BIGINT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (user_id, post_id, created_at)
) PARTITION BY RANGE (created_at);

-- For querying: "SHOW MY TIMELINE"
CREATE INDEX timeline_user_created_idx
  ON timeline (user_id, created_at DESC);

-- For cleanup: "DELETE OLD POSTS"
CREATE INDEX timeline_created_idx
  ON timeline (created_at);
```

---

## Consumer Group: Push Notifications

```javascript
async function processNewPost(message) {
  const { post } = message;

  // Get followers who have push enabled
  const pushEnabledUsers = await redis.smembers(`push:followers:${post.author_id}`);

  for (const userId of chunk(pushEnabledUsers, 100)) {
    // Send to push queue (separate topic)
    await producer.send('push-notifications', [{
      user_id: userId,
      type: 'new_post',
      title: `${post.author_name} posted`,
      body: post.content.substring(0, 100)
    }]);
  }
}
```

**Push notification topic** (high throughput, needs prioritization):

```json
{
  "event_id": "push_20241127_xyz789",
  "priority": "normal",  // or "high"
  "user_id": "user_12345",
  "notification": {
    "type": "new_post",
    "title": "...",
    "body": "...",
    "icon": "https://..."
  }
}
```

---

## Handling Failures

### Retries with Exponential Backoff

```javascript
const retry = require('async-retry');

await retry({
  retries: 5,
  factor: 2,  // 100ms, 200ms, 400ms, 800ms, 1600ms
  minTimeout: 100,
  maxTimeout: 5000
}, async (bail, attempt) => {
  const result = await sendPushNotification(notification);
  return result;
});
```

### Dead Letter Queue

```javascript
consumer.on('message', async (message) => {
  try {
    await processMessage(message);
  } catch (error) {
    if (message.headers.retryCount > 5) {
      // Move to DLQ after 5 failures
      await dlqProducer.send('timeline-dlq', message.value);
    } else {
      throw error;  // Will retry
    }
  }
});
```

### Idempotency (Exactly-Once Semantics)

```sql
CREATE TABLE timeline (
  -- ...
  PRIMARY KEY (user_id, post_id, created_at),
  UNIQUE (user_id, post_id)  -- Prevents duplicate insertion
);

-- Upsert pattern
INSERT INTO timeline (user_id, post_id, created_at)
VALUES ($1, $2, $3)
ON CONFLICT (user_id, post_id) DO NOTHING;
```

---

## Handling Queue Backpressure

### Consumer Scaling

```
Consumer Lag (messages behind) → Scale up consumers
                              → Kafka auto-balances partitions
```

### Priority Queues

```
┌─────────────────────────────────────────────────┐
│                NewPost Topic                    │
└───────────────────┬─────────────────────────────┘
                    │
        ┌───────────┴────────────┐
        │    Priority Router    │
        └──┬──────────┬──────────┬┘
           │          │          │
    ┌──────▼────┐  ┌──▼─────┐  ┌▼────────┐
    │ High      │  │ Normal │  │ Low     │
    │ Priority  │  │        │  │ Priority│
    │ Queue     │  │ Queue  │  │ Queue   │
    │ (SS)      │  │ (Kafka)│  │ (S3/DLQ) │
    └───────────┘  └────────┘  └─────────┘
```

When queue backs up:
1. **High priority**: Process immediately (SS, faster but expensive)
2. **Normal**: Process in order
3. **Low**: Defer or batch

---

## Trade-offs

| Decision | Pro | Con |
|----------|-----|-----|
| **One message per post** | Less Kafka traffic | Consumers must fetch followers |
| **Denormalized timeline** | Fast reads | More storage, eventual consistency |
| **Kafka over RabbitMQ** | Higher throughput | More infrastructure |
| **ON CONFLICT DO NOTHING** | Idempotent | Doesn't handle updates |
| **Partition by post_id** | Ordering per post | Uneven load if some posts are viral |

---

## Jargon

| Term | Definition |
|------|------------|
| **Fanout** | One message expanding to multiple recipients (like one speaker → many listeners) |
| **Eventual consistency** | System becomes consistent eventually, not immediately (seconds/minutes vs milliseconds) |
| **Message queue** | Async buffer between producers and consumers; decouples systems |
| **At-least-once** | Message guaranteed delivered, possibly multiple times (need idempotency) |
| **At-most-once** | Messages might be dropped but never duplicated (no retry) |
| **Exactly-once** | Delivered exactly once (requires idempotency + deduplication) |
| **Dead letter queue (DLQ)** | Queue for repeatedly failed messages (for investigation) |
| **Backpressure** | Signal to slow down when consumers can't keep up |
| **Consumer lag** | How far behind (messages waiting, time since oldest message) |
| **Partition** | Kafka shard; partitions in parallel allow horizontal scaling |
| **Consumer group** | Set of consumers sharing a topic; each message processed once per group |
| **Replay** | Kafka allows reading from beginning; new consumers can catch up |
| **Exponential backoff** | Retry with increasing delays: 100ms, 200ms, 400ms, 800ms... |
| **Idempotency** | Operation can be applied multiple times with same result (key for exactly-once) |

---

## Production Considerations

### Monitoring

- **Consumer lag** per consumer group
- **Messages per second** in/out
- **Error rate** by consumer
- **DLQ size** (alerts if >0)
- **Processing time** (p50, p95, p99)

### Capacity Planning

For 100K posts/day × 1000 followers:
- **100M timeline inserts/day**
- At 10K posts/hour peak: **10M inserts/hour**
- With 100 consumers: **100K inserts/consumer/hour**
- Each insert: ~1ms → **100 seconds of work per consumer** (under capacity!)

### Scaling Triggers

- Scale up when: Consumer lag > 10000 messages
- Scale down when: Consumer lag < 1000 messages for 15 minutes

---

**Next Problem:** `basic/postgres-001-index-usage/`
