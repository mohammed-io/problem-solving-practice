# Solution: Quorum Drift - Topology-Aware Quorums

---

## Root Cause

**Quorum condition (R+W > RF) assumes stable replica set.** When replicas change during write, the condition no longer guarantees overlap.

---

## Complete Solution

### Solution 1: Write Metadata with Each Operation

```go
type WriteMetadata struct {
    Timestamp      time.Time
    WriteSet       []int    // Actual replicas that acknowledged
    ReplicaVersion int64    // Version of replica topology
}

func (c *Cluster) Write(key string, value []byte, w int) error {
    replicas := c.getReplicas(key)
    var writeSet []int

    for i, replica := range replicas {
        if i >= w {
            break
        }
        if err := replica.Write(key, value); err == nil {
            writeSet = append(writeSet, replica.ID)
        }
    }

    // Store metadata alongside value
    metadata := WriteMetadata{
        Timestamp:      time.Now(),
        WriteSet:       writeSet,
        ReplicaVersion: c.topologyVersion,
    }
    c.metadata.Write(key+":metadata", metadata)

    return nil
}

func (c *Cluster) Read(key string, r int) ([]byte, error) {
    replicas := c.getReplicas(key)
    var values [][]byte
    var writeSets [][]int

    for i, replica := range replicas {
        if i >= r {
            break
        }
        value, metadata := replica.ReadWithMetadata(key)
        values = append(values, value)
        writeSets = append(writeSets, metadata.WriteSet)
    }

    // Check if read overlaps with any write
    if c.hasOverlap(writeSets, replicas[:r]) {
        return c.resolve(values), nil  // Safe: consistent read
    }

    // No overlap: potentially stale, read from all replicas
    allValues := c.readFromAll(key)
    return c.resolve(allValues), nil
}

func (c *Cluster) hasOverlap(writeSets [][]int, readReplicas []int) bool {
    for _, ws := range writeSets {
        for _, replicaID := range ws {
            if contains(readReplicas, replicaID) {
                return true  // Found overlap
            }
        }
    }
    return false
}
```

### Solution 2: Freeze Topology During Critical Operations

```go
type TopologyManager struct {
    mu               sync.RWMutex
    frozen           bool
    pendingOps       int32
    replicaSets      map[string][]int
    topologyVersion  int64
}

func (tm *TopologyManager) BeginWrite() {
    tm.mu.RLock()
    defer tm.mu.RUnlock()
    atomic.AddInt32(&tm.pendingOps, 1)
}

func (tm *TopologyManager) EndWrite() {
    atomic.AddInt32(&tm.pendingOps, -1)
}

func (tm *TopologyManager) ChangeTopology(newReplicas map[string][]int) error {
    tm.mu.Lock()

    // Wait for in-flight writes
    for atomic.LoadInt32(&tm.pendingOps) > 0 {
        time.Sleep(100 * time.Millisecond)
    }

    tm.replicaSets = newReplicas
    tm.topologyVersion++
    tm.mu.Unlock()

    return nil
}
```

### Solution 3: Merkle Tree Anti-Entropy

```
Background process:
1. Each replica maintains Merkle tree of keys
2. Periodically compare Merkle trees with another replica
3. For differing subtrees, exchange actual data
4. Update stale replicas

This handles quorum drift eventually (eventual consistency).
```

---

## Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| **Write metadata** | Detects stale reads | More storage, complex reads |
| **Freeze topology** | Simple, correct | Brief availability loss |
| **Merkle tree sync** | Eventual consistency, no stale reads forever | Background overhead |
| **Read-all on suspicion** | Always correct | Expensive reads, defeats purpose |

**Recommendation:** Write metadata + freeze topology for critical operations. Merkle tree sync for background repair.

---

**Next Problem:** `advanced/incident-108-lease-expiration/`
