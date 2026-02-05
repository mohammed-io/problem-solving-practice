# Solution: Sharded Key-Value Store Design

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Coordinator Layer                          │
│                   ( Stateless, LB-routed )                      │
│                   - Request routing                            │
│                   - Consistent hashing                          │
│                   - Retry logic                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Shard 1    │  │  Shard 2    │  │  Shard 3    │
│  (Primary)  │  │  (Primary)  │  │  (Primary)  │
│  + Replica  │  │  + Replica  │  │  + Replica  │
│  + Replica  │  │  + Replica  │  │  + Replica  │
└─────────────┘  └─────────────┘  └─────────────┘
```

---

## Component Design

### 1. Data Model

```go
type KeyValue struct {
    Key       string    `json:"key"`
    Value     []byte    `json:"value"`
    Version   int64     `json:"version"`      // Optimistic locking
    CreatedAt time.Time `json:"created_at"`
    UpdatedAt time.Time `json:"updated_at"`
    ExpiresAt *time.Time `json:"expires_at,omitempty"`  // Optional TTL
}

type StorageEngine interface {
    Get(key string) (*KeyValue, error)
    Set(kv *KeyValue) error
    Delete(key string) error
}
```

**Storage implementation:** RocksDB or LMDB (embedded, fast)

### 2. Consistent Hashing

```go
type ConsistentHash struct {
    ring        map[uint32]string  // hash → node ID
    sortedHashes []uint32           // sorted for binary search
    virtualNodes int                // virtual nodes per physical node
}

func NewConsistentHash(virtualNodes int) *ConsistentHash {
    return &ConsistentHash{
        ring:        make(map[uint32]string),
        virtualNodes: virtualNodes,  // e.g., 100
    }
}

func (ch *ConsistentHash) AddNode(nodeID string) {
    for i := 0; i < ch.virtualNodes; i++ {
        virtualKey := fmt.Sprintf("%s-%d", nodeID, i)
        hash := murmur3.Sum64([]byte(virtualKey))
        ch.ring[hash] = nodeID
        ch.sortedHashes = append(ch.sortedHashes, hash)
    }
    sort.Slice(ch.sortedHashes, func(i, j int) bool {
        return ch.sortedHashes[i] < ch.sortedHashes[j]
    })
}

func (ch *ConsistentHash) GetNode(key string) string {
    hash := murmur3.Sum64([]byte(key))

    // Binary search for next node clockwise
    idx := sort.Search(len(ch.sortedHashes), func(i int) bool {
        return ch.sortedHashes[i] >= hash
    })

    if idx == len(ch.sortedHashes) {
        idx = 0  // Wrap around
    }

    return ch.ring[ch.sortedHashes[idx]]
}
```

**Benefits of virtual nodes:**
- More even distribution
- Failed node's load distributed evenly
- Heterogenous capacity (assign more virtual nodes to powerful servers)

### 3. Replication Strategy

**Configuration:**
- Replication factor: 3
- Write quorum (W): 2
- Read quorum (R): 2
- Consistency: Strong (R + W = 4 > RF = 3)

```go
func (c *Coordinator) Set(key string, value []byte) error {
    // Find primary and replicas using consistent hash
    nodes := c.hashRing.GetNodes(key, c.replicationFactor)

    var wg sync.ErrorGroup
    successCount := 0

    for _, node := range nodes {
        node := node  // Capture for goroutine
        wg.Go(func() error {
            return c.rpcClient.Set(node, key, value)
        })
    }

    // Wait for write quorum
    if err := wg.Wait(); err != nil {
        // Log but check if quorum achieved
        c.metrics.WriteErrors.Inc()
    }

    return nil
}

func (c *Coordinator) Get(key string) (*KeyValue, error) {
    nodes := c.hashRing.GetNodes(key, c.readQuorum)

    // Read from R nodes, return most recent version
    var results []*KeyValue
    var wg sync.WaitGroup

    for i := 0; i < c.readQuorum; i++ {
        wg.Add(1)
        go func(node string) {
            defer wg.Done()
            if kv, err := c.rpcClient.Get(node, key); err == nil {
                results = append(results, kv)
            }
        }(nodes[i])
    }

    wg.Wait()

    if len(results) == 0 {
        return nil, ErrNotFound
    }

    // Return version with highest version number
    return maxVersion(results), nil
}
```

### 4. Handling Failures

**Hinted handoff:**
```go
func (c *Coordinator) SetWithHint(key string, value []byte) error {
    nodes := c.hashRing.GetNodes(key, c.replicationFactor)

    for _, node := range nodes {
        if c.isHealthy(node) {
            c.rpcClient.Set(node, key, value)
        } else {
            // Store hint on next available node
            hintNode := c.findHintNode(nodes)
            c.rpcClient.StoreHint(hintNode, node, key, value)
        }
    }
    return nil
}

// Background process: Push hints when nodes recover
func (c *Coordinator) HintPusher() {
    ticker := time.NewTicker(10 * time.Second)
    for range ticker.C {
        for _, node := range c.nodes {
            if c.isHealthy(node) {
                hints := c.rpcClient.GetHints(node)
                for _, hint := range hints {
                    c.rpcClient.Set(node, hint.Key, hint.Value)
                    c.rpcClient.DeleteHint(hint.OriginNode, hint.Key)
                }
            }
        }
    }
}
```

### 5. Rebalancing

```go
func (c *Coordinator) AddNode(nodeID string) {
    // Add to hash ring
    c.hashRing.AddNode(nodeID)

    // Calculate which keys to move
    // (Each node checks its own keys against new ring)

    // Trigger rebalancing in background
    go c.rebalance(nodeID)
}

func (c *Coordinator) rebalance(newNode string) {
    // Stream data from existing nodes to new node
    for _, node := range c.nodes {
        if node == newNode {
            continue
        }

        // Get keys that now belong to new node
        keysToMove := c.rpcClient.KeysToMove(node, newNode, c.hashRing)

        // Stream in batches
        for _, batch := range batch(keysToMove, 1000) {
            for _, key := range batch {
                kv := c.rpcClient.Get(node, key)
                c.rpcClient.Set(newNode, key, kv.Value)
                c.rpcClient.Delete(node, key)
            }
        }
    }
}
```

### 6. Handling Hot Keys

**Option A: Split hot key**
```go
// If key is hot, create N virtual keys
func getShardForKey(key string, hotKeyMap map[string]int) int {
    if replicas, isHot := hotKeyMap[key]; isHot {
        // Distribute among replicas
        suffix := rand.Intn(replicas)
        return getShard(key + ":" + strconv.Itoa(suffix))
    }
    return getShard(key)
}
```

**Option B: Local caching layer**
```
┌─────────────┐
│   Client    │ ← Local LRU cache for hot keys
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Coordinator │
└─────────────┘
```

**Option C: Read replicas for hot shard**
```go
// If shard is overloaded, add read replicas
func (s *Shard) AddReadReplica() {
    replica := NewReplica()
    s.readReplicas = append(s.readReplicas, replica)

    // Background: stream all data to replica
    go s.StreamToReplica(replica)
}
```

---

## Operational Concerns

### Monitoring

```promql
# Shard health
- alert: ShardDown
  expr: |
    up{job="kv-shard"} == 0
  for: 1m
  labels:
    severity: critical

# Hot key detection
- alert: HotKeyDetected
  expr: |
    topk(10, rate(key_reads_total[5m])) > 10000
  labels:
    severity: warning

# Rebalancing needed
- alert: ShardImbalance
  expr: |
    max(shard_size_bytes) / avg(shard_size_bytes) > 2
  labels:
    severity: warning
```

### Capacity Planning

```
Planning for 10B keys, 100 TB data:

- Per shard (with 3 replicas): ~3.3B keys, ~33 TB
- Shard size target: 1 TB per node
- Total nodes needed: 100 TB / 1 TB = 100 data nodes
- With 3 replicas: 300 physical nodes
- Coordinator nodes: 10 (stateless, can scale horizontally)

Hardware per node:
- CPU: 16 cores
- RAM: 64 GB (for caching and RocksDB)
- Disk: 2 TB NVMe SSD
- Network: 10 Gbps
```

### Deployment Strategy

```
1. Rolling upgrade
   - Upgrade one shard at a time
   - Wait for rebalancing to complete
   - Monitor for errors

2. Blue-green deployment
   - Deploy new version alongside old
   - Gradually shift traffic
   - Rollback if issues detected

3. Canary deployment
   - Deploy to 5% of shards
   - Monitor metrics
   - Gradually increase if healthy
```

---

## Trade-offs

| Decision | Option A | Option B | Recommendation |
|----------|----------|----------|----------------|
| **Sharding** | Hash | Consistent hash | Consistent hash |
| **Replication** | Synchronous | Asynchronous | Synchronous (quorum) |
| **Consistency** | Strong | Eventual | Strong (R+W > RF) |
| **Storage** | MySQL | RocksDB | RocksDB |
| **Hot keys** | Split | Cache | Both |

---

## Real Incident Reference

**Amazon DynamoDB (2012):** Introduced consistent hashing for minimal disruption during scaling. Uses virtual nodes for load distribution. Handles hot keys through partition splitting.

**Redis Cluster (2013):** Uses hash slots (16384) for consistent distribution. Automatic rebalancing when nodes added/removed.

---

**Next Problem:** `intermediate/design-011-event-sourcing/`
