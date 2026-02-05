# Step 2: Prevention and Recovery Strategies

Let's learn how to prevent CAP-related outages and recover from them.

---

## Prevention: Design for Partitions

**Rule #1: Assume partitions will happen.**

```
Layer 1: Detection
───────────────
Health checks
Ping between regions
Monitor latency spikes
Detect partition early

         ↓

Layer 2: Degradation
───────────────────
Circuit breakers
Fallback to source of truth
Queue writes for later
Graceful degradation

         ↓

Layer 3: Recovery
───────────────
Hint replay
Read repair
Full repair
Verify convergence
```

---

## Prevention Strategy 1: Health Checks

```go
package main

import (
    "fmt"
    "sync"
    "time"
)

type PartitionState int

const (
    Healthy PartitionState = iota
    Suspected
    Confirmed
    Recovering
)

type PartitionDetector struct {
    regions        []string
    state          PartitionState
    lastCheck      map[string]CheckResult
    failureCounts  map[string]int
    mu             sync.RWMutex
}

type CheckResult struct {
    Time    time.Time
    Latency time.Duration
    Status  string
}

func (d *PartitionDetector) CheckConnectivity() PartitionState {
    """Check connectivity between all regions"""
    d.mu.Lock()
    defer d.mu.Unlock()

    newState := Healthy

    for _, region := range d.regions {
        start := time.Now()

        // Ping with short timeout
        ctx, cancel := context.WithTimeout(context.Background(), 500*time.Millisecond)
        err := d.ping(ctx, region)
        cancel()

        latency := time.Since(start)

        if err == nil {
            // Reset failure count on success
            d.failureCounts[region] = 0
            d.lastCheck[region] = CheckResult{
                Time:    time.Now(),
                Latency: latency,
                Status:  "ok",
            }

            // Warn on high latency
            if latency > 300*time.Millisecond {
                log.Printf("High latency to %s: %v", region, latency)
                newState = Suspected
            }
        } else {
            d.failureCounts[region]++
            d.lastCheck[region] = CheckResult{
                Time:    time.Now(),
                Latency: 0,
                Status:  "timeout",
            }

            // 3 consecutive failures = confirmed partition
            if d.failureCounts[region] >= 3 {
                log.Printf("Partition detected to %s", region)
                newState = Confirmed
            }
        }
    }

    // State transitions
    if d.state == Confirmed && newState != Confirmed {
        d.state = Recovering
    } else {
        d.state = newState
    }

    return d.state
}

func (d *PartitionDetector) IsDegraded() bool {
    """Should we degrade service?"""
    d.mu.RLock()
    defer d.mu.RUnlock()
    return d.state == Suspected || d.state == Confirmed
}
```

---

## Prevention Strategy 2: Graceful Degradation

```go
package main

type DegradedModeService struct {
    detector *PartitionDetector
    primaryDB *PostgreSQLClient  // Source of truth
    cacheDB   *CassandraClient    // Read cache
    dlq       *KafkaProducer      // Dead letter queue
}

func (s *DegradedModeService) GetOrder(orderID string) (Order, error) {
    """Get order - always returns correct data"""
    state := s.detector.CheckConnectivity()

    if state == Healthy {
        // Fast path: read from cache
        order, err := s.cacheDB.Get("orders:" + orderID)
        if err == nil {
            return order, nil
        }
    }

    // Fallback: read from source of truth
    return s.primaryDB.Query(
        fmt.Sprintf("SELECT * FROM orders WHERE id = '%s'", orderID),
    )
}

func (s *DegradedModeService) CreateOrder(orderData map[string]interface{}) (string, error) {
    """Create order - never loses data"""
    state := s.detector.CheckConnectivity()

    // Always write to primary (source of truth)
    orderID, err := s.primaryDB.Insert("orders", orderData)
    if err != nil {
        log.Printf("Cannot write to primary: %v", err)
        return "", fmt.Errorf("service unavailable")
    }

    // Async: update cache
    if state == Healthy {
        err := s.cacheDB.Set("orders:"+orderID, orderData)
        if err != nil {
            // Cache update failed - will retry later
            log.Printf("Cache update failed: %v", err)
            s.scheduleCacheUpdate(orderID, orderData)
        }
    } else {
        // Partition detected - queue cache update for later
        s.dlq.Produce(map[string]interface{}{
            "operation": "update_cache",
            "order_id":  orderID,
            "data":      orderData,
        })
    }

    return orderID, nil
}

func (s *DegradedModeService) scheduleCacheUpdate(orderID string, data map[string]interface{}) {
    """Schedule background task to update cache"""
    time.AfterFunc(1*time.Minute, func() {
        s.updateCache(orderID, data)
    })
}

func (s *DegradedModeService) updateCache(orderID string, data map[string]interface{}) {
    """Background task to update cache"""
    err := s.cacheDB.Set("orders:"+orderID, data)
    if err != nil {
        // Still failing - reschedule
        log.Printf("Cache update retry failed: %v", err)
        s.scheduleCacheUpdate(orderID, data)
    }
}
```

---

## Prevention Strategy 3: Fix Hot Spots

```go
package main

import (
    "crypto/sha256"
    "encoding/binary"
    "math"
)

// BAD: Sharding by first character (creates hot spots)
func badShard(key string, numShards int) int {
    """Don't do this!"""
    return int(key[0]) % numShards
}

// BETTER: Consistent hashing
func betterShard(key string, numShards int) int {
    """Use consistent hashing"""
    hash := sha256.Sum256([]byte(key))
    // Use first 8 bytes as uint64
    hashInt := binary.BigEndian.Uint64(hash[:8])
    return int(hashInt % uint64(numShards))
}

// BEST: Use a consistent hash ring
type ConsistentHash struct {
    replicas int
    ring     map[uint64]string
    keys     []uint64
}

func NewConsistentHash(nodes []string, replicas int) *ConsistentHash {
    ch := &ConsistentHash{
        replicas: replicas,
        ring:     make(map[uint64]string),
        keys:     make([]uint64, 0),
    }

    for _, node := range nodes {
        ch.AddNode(node)
    }

    return ch
}

func (ch *ConsistentHash) AddNode(node string) {
    """Add a node to the ring"""
    for i := 0; i < ch.replicas; i++ {
        key := ch.hash(fmt.Sprintf("%s:%d", node, i))
        ch.ring[key] = node
        ch.keys = append(ch.keys, key)
    }
    ch.sortKeys()
}

func (ch *ConsistentHash) GetNode(key string) string {
    """Get the node for a given key"""
    if len(ch.ring) == 0 {
        return ""
    }

    hash := ch.hash(key)

    // Find first node with key >= hash
    for _, ringKey := range ch.keys {
        if ringKey >= hash {
            return ch.ring[ringKey]
        }
    }

    // Wrap around to first node
    return ch.ring[ch.keys[0]]
}

func (ch *ConsistentHash) hash(value string) uint64 {
    hash := sha256.Sum256([]byte(value))
    return binary.BigEndian.Uint64(hash[:8])
}

func (ch *ConsistentHash) sortKeys() {
    // Sort keys in ascending order
    sort.Slice(ch.keys, func(i, j int) bool {
        return ch.keys[i] < ch.keys[j]
    })
}
```

---

## Recovery: Handling Hint Overflow

```go
package main

type HintManager struct {
    cassandra       *CassandraClient
    alertThreshold  int
    criticalThreshold int
}

func (m *HintManager) CheckHints() (map[string]int, error) {
    """Check hint status across the cluster"""
    result, err := m.cassandra.RunNodetool("statshints")
    if err != nil {
        return nil, err
    }

    hints := make(map[string]int)
    // Parse output like: "127.0.0.1: 5423 hints"
    // Implementation depends on nodetool output format

    for node, count := range hints {
        if count > m.criticalThreshold {
            log.Printf("CRITICAL hint overflow on %s: %d", node, count)
        } else if count > m.alertThreshold {
            log.Printf("HINT overflow on %s: %d", node, count)
            alert.Send(fmt.Sprintf("Hint count: %d on %s", count, node))
        }
    }

    return hints, nil
}

func (m *HintManager) IsHintOverflow() bool {
    """Check if any node has too many hints"""
    hints, _ := m.CheckHints()

    for _, count := range hints {
        if count > m.criticalThreshold {
            return true
        }
    }
    return false
}

func (m *HintManager) TriggerHintReplay() error {
    """Manually trigger hint delivery"""
    result, err := m.cassandra.RunNodetool("replayhintlog")

    // Monitor progress
    hintsBefore, _ := m.CheckHints()

    log.Info("Hint replay triggered, monitoring...")

    for i := 0; i < 60; i++ {
        time.Sleep(1 * time.Second)
        hintsNow, _ := m.CheckHints()

        // Check if hints are decreasing
        totalBefore := sumValues(hintsBefore)
        totalNow := sumValues(hintsNow)

        if totalNow < totalBefore {
            log.Printf("Hints decreasing: %d -> %d", totalBefore, totalNow)
        } else {
            log.Printf("Hints NOT decreasing: %d", totalNow)
        }
    }

    hintsAfter, _ := m.CheckHints()
    log.Printf("Hint replay complete. Before: %v, After: %v", hintsBefore, hintsAfter)

    return err
}
```

---

## Recovery: Running Repair

```go
package main

type RepairManager struct {
    cassandra *CassandraClient
}

func (m *RepairManager) RepairKeyspace(keyspace string, parallel bool) error {
    """Run repair on a keyspace"""
    options := ""
    if parallel {
        options = "-pr"  // Parallel repair
    }

    cmd := fmt.Sprintf("repair %s %s", keyspace, options)

    log.Infof("Starting repair: %s", cmd)
    result, err := m.cassandra.RunNodetool(cmd)
    if err != nil {
        return err
    }
    log.Infof("Repair complete: %s", result)

    return nil
}

func (m *RepairManager) RepairTable(keyspace, table string) error {
    """Run repair on a specific table"""
    cmd := fmt.Sprintf("repair %s %s", keyspace, table)
    log.Infof("Starting table repair: %s", cmd)
    result, err := m.cassandra.RunNodetool(cmd)
    if err != nil {
        return err
    }
    log.Infof("Table repair complete: %s", result)

    return nil
}

func (m *RepairManager) ScheduleRepair() {
    """Schedule regular repairs"""
    // Full repair: weekly on Sunday at 2 AM
    // Use cron or similar scheduler

    // Incremental repair: daily at 3 AM
    log.Info("Repair schedule configured")
}
```

---

## Runbook: Handling a Partition

```
RUNBOOK: Cassandra Partition Detected
─────────────────────────────────────

Severity: P1 (data loss risk)

1. DETECTION (Automated)
   ├── Monitor: nodetool statshints > 10000
   ├── Monitor: nodetool netstats shows dropped mutations
   └── Alert sent to on-call

2. ASSESSMENT (5 minutes)
   ├── Check nodetool status (which nodes are down?)
   ├── Check network (is this a known partition?)
   ├── Check application logs (impact assessment)
   └── Determine: Is this a partition or node failure?

3. IMMEDIATE ACTIONS (10 minutes)
   ├── If partition: EXPECT DEGRADATION
   │   ├── Change CL to ONE for non-critical reads
   │   ├── Enable fallback to source of truth
   │   └── Monitor for data divergence
   │
   └── If node failure: REPLACE NODE
       ├── Add replacement node
       ├── Stream data from healthy nodes
       └── Repair after bootstrap

4. RECOVERY (After partition heals)
   ├── Replay hints: nodetool replayhintlog
   ├── Run repair: nodetool repair -pr
   ├── Verify consistency: SELECT COUNT(*) on all nodes
   └── Monitor for 24 hours

5. POST-MORTEM
   ├── Root cause analysis
   ├── Update runbook if needed
   ├── Improve detection
   └── Schedule chaos engineering test
```

---

## Summary

| Layer | Tool | Action |
|-------|------|--------|
| Detection | nodetool, Prometheus | Monitor hints, latency |
| Prevention | Health checks, circuit breakers | Fail fast to source |
| Degradation | Fallback, DLQ | Queue for later |
| Recovery | repair, replayhintlog | Sync replicas |
| Verification | queries, checksums | Confirm convergence |

**Key principle:** During a partition, prioritize **data correctness** over **low latency**. It's better to return an error or stale data than to lose data.

---

## Quick Check

Before moving on, make sure you understand:

1. What's the three-layer prevention strategy? (Detection → Degradation → Recovery)
2. How do health checks detect partitions? (Ping with short timeout, track consecutive failures)
3. What's graceful degradation? (Fallback to source of truth when cache is unavailable)
4. Why avoid hot spots in sharding? (Creates uneven load, can overwhelm single node during partition)
5. What's the repair runbook? (Detect → Assess → Immediate action → Recovery → Post-mortem)

---

**Next:** Practice with the other CAP-related problems.
