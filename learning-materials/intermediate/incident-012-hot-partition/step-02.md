# Step 02: Implementing Solutions

---

## Immediate Mitigation

### 1. Add Consumer for Hot Partition

```javascript
// Add dedicated consumer for p-4
const hotConsumer = new KafkaConsumer({
  'group.id': 'hot-partition-consumer',
  'bootstrap.servers': 'kafka:9092',
  'assignment.strategy': 'manual'  // Manually assign p-4
});

hotConsumer.assign([{ topic: 'messages', partition: 4 }]);

// Now p-4 has 2 consumers sharing load
```

### 2. Increase Partitions

```bash
# Kafka doesn't support decreasing partitions!
# But we can increase:

kafka-topics.sh --bootstrap-server localhost:9092 \
  --alter --topic messages \
  --partitions 64

# Reassign consumers to new partitions
kafka-reassign-partitions.sh --bootstrap-server localhost:9092 \
  --topics-to-move-json-file topics.json \
  --execute
```

---

## Implementation: Composite Key

```javascript
// Producer: Use composite key
const partitionKey = `${channelId}:${Math.floor(Date.now() / 60000)}`; // 1-minute buckets

producer.send({
  topic: 'messages',
  messages: [{
    key: partitionKey,
    value: JSON.stringify(message),
    headers: {
      'channel_id': channelId,
      'timestamp': Date.now().toString()
    }
  }]
});

// Consumer: Reassemble by channel
const messagesByChannel = new Map();

consumer.on('data', (message) => {
  const channelId = message.headers['channel_id'];
  if (!messagesByChannel.has(channelId)) {
    messagesByChannel.set(channelId, []);
  }
  messagesByChannel.get(channelId).push(message);

  // Emit in order per channel
  if (shouldEmit(messagesByChannel.get(channelId))) {
    emitToClients(channelId, messagesByChannel.get(channelId));
    messagesByChannel.set(channelId, []);
  }
});
```

---

## Implementation: Salting

```javascript
// Producer: Salt with user_id
const partitionKey = `${channelId}:${userId}`;

producer.send({
  topic: 'messages',
  messages: [{
    key: partitionKey,
    value: JSON.stringify(message)
  }]
});

// Now messages in #general spread across partitions based on user
// Each consumer sees subset of users
// Need to broadcast to all users in channel (different pattern)
```

---

## Implementation: Smart Consumer Scaling

```javascript
class PartitionMonitor {
  async checkLag() {
    const admin = kafka.admin();
    const group = 'chat-consumers';

    const lag = await admin.fetchOffsets({ groupId: group });

    for (const [topic, partitions] of Object.entries(lag)) {
      for (const [partition, info]) of Object.entries(partitions)) {
        if (info.lag > 10000) {  // 10k messages behind
          await this.addConsumer(topic, partition);
        }
      }
    }
  }

  async addConsumer(topic, partition) {
    // Spin up new consumer for this partition
    const newConsumer = new KafkaConsumer({
      'group.id': `chat-consumer-${partition}`,
      'bootstrap.servers': 'kafka:9092'
    });

    newConsumer.subscribe({ topic, partition });
    newConsumer.consume();
  }
}

setInterval(() => monitor.checkLag(), 30000); // Every 30 seconds
```

---

## Prevention: Design Principles

### 1. Partition by "Entity" Not "Topic"

```
❌ BAD: All #general messages to one partition
✅ GOOD: Each user's messages distributed

Think: Who is the consumer? What ordering do they need?
```

### 2. Design for Virality

```
Assume: Any channel can become #general
Plan: Auto-scale infrastructure
Monitor: Per-partition metrics
```

### 3. Fallback Strategies

```javascript
async function sendMessage(message) {
  try {
    await producer.send(message);
  } catch (e) {
    if (e.code === 'QUEUE_FULL') {
      // Backpressure - queue or reject
      await retryQueue.add(message);
    }
  }
}
```

---

## Monitoring Setup

```yaml
# Prometheus alerts for hot partitions
groups:
  - name: kafka
    rules:
      - alert: HotPartitionDetected
        expr: kafka_consumer_lag > 10000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Partition {{ $labels.partition }} has lag {{ $value }}"

      - alert: ConsumerBehind
        expr: kafka_consumed_offset / kafka_produced_offset < 0.9
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Consumer {{ $labels.consumer }} is 10%+ behind"
```

---

## Summary

| Fix Type | Solution | Timeframe |
|----------|----------|-----------|
| **Immediate** | Add dedicated consumer for hot partition | Minutes |
| **Short-term** | Increase partitions | Hours |
| **Long-term** | Redesign partitioning strategy | Days-Sprint |
| **Prevention** | Monitoring + auto-scaling | Always |

---

## Quick Check

Before moving on, make sure you understand:

1. What's the immediate fix for hot partition? (Add dedicated consumer for hot partition)
2. Why can't you decrease Kafka partitions? (Kafka doesn't support decreasing partitions)
3. What's a composite partition key? (Combining multiple fields like channel_id + timestamp)
4. What's the trade-off with salting? (Spreads load but requires complex consumer logic)
5. How do you monitor for hot partitions? (Per-partition lag metrics, alert when lag > threshold)

---

**Now read `solution.md` for complete reference.**
