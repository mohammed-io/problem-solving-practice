# Step 1: Why CL=QUORUM Didn't Help

Let's analyze why this system failed despite using QUORUM consistency.

---

## The Misconception

**Team thought:** `CL=QUORUM` means "strong consistency"

**Reality:** `CL=QUORUM` only guarantees "majority consistency"

```
What They Expected:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CL=QUORUM on Read
────────────────
Returns most recent write
Always consistent
No stale data

CL=QUORUM on Write
────────────────
Waits for majority
Durable writes
No data loss

What Actually Happened:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CL=QUORUM on Read
────────────────
Returns data from 2 of 3 nodes
If 1 node is stale, might read stale!
Depends on which nodes respond

CL=QUORUM on Write
────────────────
Waits for 2 of 3 nodes
If 1 node is down, still succeeds
Data written to 2 nodes
Stale node doesn't get it!
```

---

## The Failure Mode

**Normal state (3 nodes, RF=3):**
```
Node A (AZ-A): Data v1
Node B (AZ-B): Data v1
Node C (AZ-C): Data v1

Write with CL=QUORUM (2 of 3):
- Write v2 to A and B
- C async replicates
- All have v2 eventually ✓

Read with CL=QUORUM (2 of 3):
- Read from any 2 nodes
- Both have v2 (or latest)
- Returns v2 ✓
```

**During partition (AZ-A isolated):**
```
Node A (AZ-A): Data v1, can't reach others
Node B (AZ-B): Data v2, connected to C
Node C (AZ-C): Data v2, connected to B

Write with CL=QUORUM (2 of 3):
- Can only reach B and C
- Write v3 to B and C
- A doesn't get v3 (isolated)
- A still has v1!

Read with CL=QUORUM (2 of 3):
- Might read from A + B
- A has v1, B has v2
- Which to return?
- Depends on which responds first!
- Can return stale data! ✗
```

---

## Question 1: Why did QUORUM not prevent stale reads?

**Answer:** **QUORUM doesn't guarantee you read from the latest replicas**

```
Client → read(key, CL=QUORUM)
Driver: Need 2 of 3 responses

Driver → Node A: Request read
Node A → Driver: v1 (stale!)

Driver → Node B: Request read
Node B → Driver: v2 (fresh)

Driver: Got 2 responses
Driver: A=v1, B=v2
Driver: Which to return?

Possible outcomes:
- Driver picks first response → v1 (STALE!)
- Driver picks by timestamp → v2 (correct)
- Driver reads from A + C → v1 + v1 (both stale!) → v1 (STALE!)
```

**The problem:** Cassandra's read coordinator might read from the stale nodes!

**Solution:** Use `CL=ALL` or `serial` consistency for critical reads

---

## Question 2: Is CQRS with Read Cache Inherently AP?

**Answer:** **Yes, if the read cache can diverge from source of truth**

```
Write Side (PostgreSQL)
───────────────────────
Source of Truth
Strong Consistency
Always Correct

         ↓

Event Queue (Kinesis)
─────────────────────
Reliable delivery
Ordered events

         ↓

Processor (Lambda)
───────────────────
May fail
May retry
May delay

         ↓

Read Side (Cassandra)
─────────────────────
Eventual consistency
May be stale
May be missing
```

**During failure:**
```
T1: Order created in PostgreSQL
T2: Event published to Kinesis
T3: Cassandra unavailable (partition)
T4: Lambda backs off, retries
T5: User queries: "Where is my order?"
T6: Cassandra query: Not found!
T7: PostgreSQL: Order exists!

Result: Inconsistent view!
```

**This is AP by design.**

---

## Question 3: How to Detect Partition and Fail Fast?

**Answer:** **Health checks + circuit breaker**

```go
package main

import (
    "fmt"
    "time"
)

type ClusterHealth int

const (
    Healthy ClusterHealth = iota
    Degraded
    Unavailable
)

type CassandraCluster struct {
    contactPoints []string
    timeout       time.Duration
    health        ClusterHealth
    lastCheck     time.Time
}

func (c *CassandraCluster) CheckHealth() ClusterHealth {
    """Check cluster health via lightweight query"""
    now := time.Now()
    if now.Sub(c.lastCheck) < 5*time.Second {
        return c.health
    }

    c.lastCheck = now

    // Lightweight query to local node
    ctx, cancel := context.WithTimeout(context.Background(), c.timeout)
    defer cancel()

    err := c.session.Query("SELECT now() FROM system.local LIMIT 1").
        Consistency(gocql.One).
        WithContext(ctx).
        Exec()

    if err == nil {
        c.health = Healthy
    } else if err == context.DeadlineExceeded {
        // Query timed out - degraded!
        c.health = Degraded
    } else {
        // Can't reach any host - unavailable!
        c.health = Unavailable
    }

    return c.health
}

func (c *CassandraCluster) ReadWithFallback(key string) (interface{}, error) {
    health := c.CheckHealth()

    if health == Unavailable {
        // Fail fast to PostgreSQL
        log.Printf("Cassandra unavailable, using PostgreSQL for %s", key)
        return c.readFromPostgres(key)
    }

    if health == Degraded {
        // Try Cassandra, but short timeout
        ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
        defer cancel()

        result, err := c.readFromCassandraContext(ctx, key)
        if err != nil {
            log.Printf("Cassandra degraded, using PostgreSQL for %s", key)
            return c.readFromPostgres(key)
        }
        return result, nil
    }

    // Healthy: Use Cassandra
    return c.readFromCassandra(key)
}
```

---

## Question 4: When is Hinted Handoff Dangerous?

**Answer:** **When hints overflow, data is silently dropped**

```
Normal Path:
─────────────
Write to replicas
Wait for CL=QUORUM
Return success

Hint Path (replica down):
─────────────────────────
Write to available replicas
Store hint for down replica
Return success

Replay (when replica recovers):
──────────────────────────────
Detect replica is back
Send all hints
Replica catches up

Overflow (too many hints):
───────────────────────────
Hint storage: 500MB (default)
At 50KB/hint = ~10,000 hints
At 50K writes/min with 30% hints
= 15K hints/min
Storage exhausted in ~40 seconds!

New hints: DROPPED!
Result: Silent data loss!
```

**Monitoring to prevent overflow:**
```bash
# Check hint count
nodetool statshints

# Check if hints are being delivered
nodetool netstats | grep "Repair"

# Alert if:
# - hint_count > 100,000
# - hint_storage > 80% full
# - hints not decreasing over time
```

---

## Question 5: Redesign for Partition Safety

```go
package main

type BetterOrderSystem struct {
    pg        *PostgreSQLClient  // Source of truth
    kafka     *KafkaClient        // Durable events
    cassandra *CassandraClient    // Read cache
    dlq       *KafkaProducer      // Dead letter queue
}

func (s *BetterOrderSystem) CreateOrder(orderData Order) (string, error) {
    """Create order - CP for write"""
    // Write to PostgreSQL (strong consistency)
    orderID, err := s.pg.Execute(
        "INSERT INTO orders ... VALUES (...) RETURNING id",
        orderData,
    )
    if err != nil {
        return "", err
    }

    // Publish event to Kafka (durable)
    s.kafka.Produce("order-created", map[string]interface{}{
        "order_id": orderID,
        "data":     orderData,
        "timestamp": time.Now().Unix(),
    })

    return orderID, nil
}

func (s *BetterOrderSystem) GetOrder(orderID string) (Order, error) {
    """Get order - AP with fallback"""
    // Try Cassandra first (fast)
    result, err := s.cassandra.Query(
        fmt.Sprintf("SELECT * FROM orders WHERE id = %s", orderID),
        100*time.Millisecond, // Short timeout
    )
    if err == nil && result != nil {
        return result, nil
    }

    // Fallback to PostgreSQL (correct)
    log.Printf("Fallback to PostgreSQL for %s", orderID)
    return s.pg.Query(
        fmt.Sprintf("SELECT * FROM orders WHERE id = %s", orderID),
    )
}

func (s *BetterOrderSystem) ProcessOrderEvent(event OrderEvent) error {
    """Process order event - update read cache"""
    err := s.cassandra.Execute(
        fmt.Sprintf("INSERT INTO orders ... VALUES (%s, ...)", event.OrderID),
    )
    if err != nil {
        // Write to DLQ instead of dropping!
        s.dlq.Produce(map[string]interface{}{
            "event": event,
            "error": err.Error(),
            "timestamp": time.Now().Unix(),
        })
        metrics.Increment("cassandra.dlq")

        // Alert ops team if DLQ is growing
        dlqDepth := s.dlq.GetDepth()
        if dlqDepth > 1000 {
            alert.Send(fmt.Sprintf("Order DLQ depth: %d", dlqDepth))
        }
    }
    return err
}
```

---

## Summary

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Stale reads | CL=QUORUM doesn't prevent reading from stale replicas | Use CL=ALL or fallback to source |
| Data loss | Hint overflow | Use DLQ, monitor hints |
| Slow detection | No health checks | Add health checks with circuit breaker |
| Silent failures | No monitoring for dropped mutations | Monitor nodetool tpstats |
| Poor UX | Changed CL to ONE (worse) | Should have failed fast to PostgreSQL |

---

## Quick Check

Before moving on, make sure you understand:

1. Why did CL=QUORUM not prevent stale reads? (QUORUM reads from 2 of 3 nodes, but those nodes might not be the freshest ones)
2. Is CQRS with read cache inherently AP? (Yes, if the read cache can diverge from source of truth during failure)
3. How do you detect a network partition? (Health checks with short timeouts, monitor latency and response times)
4. When is hinted handoff dangerous? (When hints overflow storage limit, new hints are silently dropped)
5. What's the pattern for safe CQRS? (Always write to source of truth, use DLQ for failed cache updates, fallback on read)

---

**Proceed to `step-02.md`**
