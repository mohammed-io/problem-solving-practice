# Solution: Consistent Hashing

---

## Complete Implementation

```go
package consistent

import (
    "fmt"
    "sort"
    "github.com/spaolacci/murmur3"
)

type ConsistentHash struct {
    ring         map[uint32]string
    sortedHashes []uint32
    virtualNodes int
}

func New(virtualNodes int) *ConsistentHash {
    return &ConsistentHash{
        ring:         make(map[uint32]string),
        virtualNodes: virtualNodes,
    }
}

func (ch *ConsistentHash) AddNode(nodeID string) {
    for i := 0; i < ch.virtualNodes; i++ {
        virtualKey := fmt.Sprintf("%s-%d", nodeID, i)
        hash := murmur3.Sum64([]byte(virtualKey))
        ch.ring[uint32(hash)] = nodeID
    }

    ch.rebuildSortedHashes()
}

func (ch *ConsistentHash) RemoveNode(nodeID string) {
    for i := 0; i < ch.virtualNodes; i++ {
        virtualKey := fmt.Sprintf("%s-%d", nodeID, i)
        hash := murmur3.Sum64([]byte(virtualKey))
        delete(ch.ring, uint32(hash))
    }

    ch.rebuildSortedHashes()
}

func (ch *ConsistentHash) rebuildSortedHashes() {
    ch.sortedHashes = make([]uint32, 0, len(ch.ring))
    for hash := range ch.ring {
        ch.sortedHashes = append(ch.sortedHashes, hash)
    }
    sort.Slice(ch.sortedHashes, func(i, j int) bool {
        return ch.sortedHashes[i] < ch.sortedHashes[j]
    })
}

func (ch *ConsistentHash) GetNode(key string) string {
    if len(ch.ring) == 0 {
        return ""
    }

    hash := murmur3.Sum64([]byte(key))

    idx := sort.Search(len(ch.sortedHashes), func(i int) bool {
        return ch.sortedHashes[i] >= uint32(hash)
    })

    if idx == len(ch.sortedHashes) {
        idx = 0  // Wrap around
    }

    return ch.ring[ch.sortedHashes[idx]]
}

func (ch *ConsistentHash) GetNodes(key string, count int) []string {
    if len(ch.ring) == 0 {
        return nil
    }

    hash := murmur3.Sum64([]byte(key))

    var nodes []string
    seen := make(map[string]bool)

    for i := 0; i < len(ch.sortedHashes) && len(nodes) < count; i++ {
        idx := (sort.Search(len(ch.sortedHashes), func(i int) bool {
            return ch.sortedHashes[i] >= uint32(hash)
        }) + i) % len(ch.sortedHashes)

        node := ch.ring[ch.sortedHashes[idx]]
        if !seen[node] {
            seen[node] = true
            nodes = append(nodes, node)
        }
    }

    return nodes
}
```

---

## Heterogeneous Capacities

For servers with different capacities:

```go
func (ch *ConsistentHash) AddNodeWithWeight(nodeID string, weight int) {
    // More virtual nodes = more capacity
    virtualNodes := ch.virtualNodes * weight

    for i := 0; i < virtualNodes; i++ {
        virtualKey := fmt.Sprintf("%s-%d", nodeID, i)
        hash := murmur3.Sum64([]byte(virtualKey))
        ch.ring[uint32(hash)] = nodeID
    }

    ch.rebuildSortedHashes()
}
```

---

## Handling Hot Keys

```go
// Split hot key across multiple servers
func (ch *ConsistentHash) GetNodesForKey(key string, replicas int) []string {
    return ch.GetNodes(key, replicas)
}

// For hot keys, use different sub-keys
func GetWithHotKeyReplicas(key string, replicas int, ch *ConsistentHash) []string {
    var nodes []string
    for i := 0; i < replicas; i++ {
        subKey := fmt.Sprintf("%s-%d", key, i)
        node := ch.GetNode(subKey)
        nodes = append(nodes, node)
    }
    return nodes
}
```

---

## Trade-offs

| Aspect | Option A | Option B |
|--------|----------|----------|
| **Virtual nodes** | Few (10-50) | Many (100-1000) |
| **Distribution** | Less even | More even |
| **Memory** | Lower | Higher |
| **Lookup** | Faster | Slower (binary search) |

**Recommendation:** 100-200 virtual nodes per physical node.

---

## Real Implementations

- **DynamoDB, Cassandra, Riak:** Use consistent hashing
- **Memcached, Redis Cluster:** Use consistent hashing with virtual nodes
- **Akamai CDN:** Original use case for consistent hashing

---

**Next Problem:** `advanced/design-101-idempotency/`
