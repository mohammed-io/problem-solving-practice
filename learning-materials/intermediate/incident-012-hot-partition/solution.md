# Solution: Hot Partition - Hash-based Partitioning on Skewed Data

---

## Root Cause

**Simple hash partitioning on `channel_id`** causes skewed distribution when some channels are significantly more popular than others.

```
hash("general") % 32 = 4  → 500K messages/day
hash("random-123") % 32 = 11 → 50 messages/day
```

When a channel goes viral (news event, celebrity joins), all its traffic goes to one partition.

---

## Immediate Fixes

### Fix 1: Add Partitions to Hot Topic

```bash
# Increase partitions from 32 to 64
kafka-topics.sh --alter --topic messages --partitions 64
```

But this just splits the problem - #general now maps to 2 partitions instead of 1.

### Fix 2: Add More Consumers for Partition 4

Deploy additional consumer instances:

```yaml
consumers:
  - name: consumer-4a
    partitions: [4]
  - name: consumer-4b
    partitions: [4]  # Extra consumer for hot partition
```

Kafka allows multiple consumers per partition **in the same group** using `assignor`.

---

## Long-term Solutions

### Solution 1: Salting (Add Randomness)

```javascript
function getPartition(channelId, numPartitions) {
  // Try different salts until finding a balanced partition
  const salts = [0, 1, 2, 3, 4];

  for (const salt of salts) {
    const partition = hash(`${channelId}:${salt}`) % numPartitions;

    // Check if this partition is overloaded
    if (getLag(partition) < THRESHOLD) {
      return partition;
    }
  }

  // Fallback to original hash
  return hash(channelId) % numPartitions;
}
```

When producing messages:
```javascript
const partition = getPartition(channelId, 64);
producer.send({ topic: 'messages', partition });
```

### Solution 2: Two-Level Partitioning

```
messages topic (128 partitions)
├── Primary partition: hash(channel_id) % 64
└── Sub-partition: hash(message_id) % 2

Each channel actually spans 2 partitions!
```

Consumer for p-4 reads from p-4.0 and p-4.1.

### Solution 3: Separate High-Volume Topics

```
high-volume-messages (32 partitions) ← For channels like #general
regular-messages (32 partitions)     ← For normal channels
```

Route based on channel type:
```javascript
const topic = isHighVolumeChannel(channelId)
  ? 'high-volume-messages'
  : 'regular-messages';
```

---

## Systemic Prevention (Staff Level)

### 1. Monitor Partition Skew

```sql
-- Track messages per partition
SELECT
  partition,
  COUNT(*) as message_count,
  NOW() - MAX(timestamp) as lag_seconds
FROM consumer_metrics
WHERE timestamp > NOW() - INTERVAL '5 minutes'
GROUP BY partition
HAVING COUNT(*) > 10000;  -- Alert on hot partitions
```

### 2. Auto-Rebalancing

```javascript
// Background job checks every minute
async function rebalanceHotPartitions() {
  const stats = await getPartitionStats();

  for (const [partition, lag] of Object.entries(stats)) {
    if (lag > 10000) {  // 10 seconds
      await addConsumerToPartition(partition);
    }
  }
}
```

### 3. Move to Stream Processing

Instead of storing messages by channel, store as stream:

```
┌────────────────────────────────────────────────────────┐
│                  messages stream                     │
│  Partition by user_id (not channel_id)               │
│  Each consumer processes messages for its users     │
│  Consumers maintain per-user timelines locally       │
└────────────────────────────────────────────────────────┘
```

This eliminates channel-level hot spots.

---

## Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| **Add partitions** | Simple, no code change | Rebalancing required, eventual limit |
| **Salting** | Better distribution | More complex producer logic |
| **Two-level partitioning** | Good balance | More partitions, complex routing |
| **Separate topics** | Isolation, independent scaling | More topics to manage |
| **Stream processing** | Eliminates hot spots | Different mental model, need rebuild |

For social messaging: **Two-level partitioning** is a good balance.

---

## Real Incident

**Slack (2020)**: HBase hot partition caused message delays. Popular channels overloaded single partitions, causing delays. Fix: Changed partitioning strategy to use salting and added more capacity.

---

## Jargon

| Term | Definition |
|------|------------|
| **Hot partition** | Partition receiving disproportionately high traffic; creates bottleneck |
| **Skew** | Uneven distribution of data across partitions |
| **Salting** | Adding random suffix to partition key to distribute load |
| **Rebalancing** | Kafka process of reassigning partitions when consumers join/leave |
| **Consumer group** | Set of consumers; each partition consumed by exactly one consumer |
| **Backpressure** | Signal to slow down when consumers can't keep up |
| **Producer** | Application sending messages to Kafka |
| **Consumer** | Application reading messages from Kafka |
| **Lag** | Messages in queue minus messages processed |
| **Assignor** | Kafka component that decides which consumer gets which partition |

---

**Next Problem:** `intermediate/incident-013-deadlock/`
