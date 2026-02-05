# Step 2: Preventing Quorum Drift

---

## Solution 1: Quorum Versions

Track replica set version with each write:

```go
type WriteContext struct {
    ReplicaSetVersion int64  // Increments on topology change
    Replicas         []int   // Actual replicas written to
}

func (db *Database) Write(key string, value []byte, w int) error {
    ctx := WriteContext{
        ReplicaSetVersion: db.currentVersion,
    }

    replicas := db.getReplicasForKey(key)
    for _, replica := range replicas[:w] {
        if err := replica.Write(key, value, ctx.ReplicaSetVersion); err != nil {
            return err
        }
        ctx.Replicas = append(ctx.Replicas, replica.ID)
    }

    // Store write metadata
    db.metadata.Write(key, ctx)
    return nil
}

func (db *Database) Read(key string, r int) ([]byte, error) {
    replicas := db.getReplicasForKey(key)
    results := make([][]byte, 0, r)

    for _, replica := range replicas[:r] {
        value, version, replicas := replica.Read(key)
        results = append(results, value)

        // Check if any of written replicas are in read set
        writeCtx := db.metadata.Get(key)
        for _, writtenReplica := range writeCtx.Replicas {
            if contains(replicas, writtenReplica) {
                return merge(results), nil  // Safe: we overlap
            }
        }
    }

    // No overlap: might be stale
    return merge(results), ErrPotentiallyStale
}
```

---

## Solution 2: Block Writes During Topology Change

```go
func (cm *ClusterManager) RemoveNode(nodeID int) error {
    // Quorum writes block during topology change
    cm.blockingMode.Store(true)
    defer cm.blockingMode.Store(false)

    // Wait for all pending writes
    cm.waitForInProgressWrites()

    // Update topology
    cm.replicaSets = cm.newReplicaSetsWithout(nodeID)

    return nil
}
```

**Trade-off:** Brief write availability interruption for consistency.

---

## Solution 3: Read Repair from Source

```
If read detects potential stale data:
1. Fetch from all replicas (not just R)
2. Find latest version by timestamp/version
3. Update stale replicas
4. Return latest to client
```

---

## Quick Check

Before moving on, make sure you understand:

1. What are quorum versions? (Track replica set version with writes)
2. How do versions prevent drift? (Detect when replica set changed)
3. Why block writes during topology change? (Ensure no in-flight writes)
4. What is read repair? (Fetch from all replicas, update stale ones)
5. What's the tradeoff of blocking writes? (Brief availability interruption)

---

**Continue to `solution.md`**
