# Step 03: Virtual Nodes for Even Distribution

---

## The Problem: Uneven Distribution

With few physical servers, keys can distribute unevenly.

```
Ring with 3 servers:
Server A at position: 100
Server B at position: 2000
Server C at position: 4000

Hash space: 0 to 2^32 (4 billion)

Ranges:
A: 0-100 (tiny! 100 keys)
B: 100-2000 (medium, 1900 keys)
C: 2000-4B (huge! rest of ring)

Server C gets 99.97% of keys!
```

---

## Solution: Virtual Nodes

Each physical server appears **multiple times** on the ring.

```
Physical servers: 3
Virtual nodes per server: 100

Virtual nodes:
A-0, A-1, A-2, ..., A-99  (each different hash)
B-0, B-1, B-2, ..., B-99
C-0, C-1, C-2, ..., C-99

Total points on ring: 300
```

**Result:** Each server gets ~1/3 of the ring (balanced!).

---

## Visual: Virtual Nodes

```
Before (uneven):
○ A                           ○ B (huge gap)
       \_________________________/
              Server C gets everything

After (virtual nodes):
A-0 ○  A-5 ○  A-10 ○  B-3 ○  B-8 ○  C-1 ○  C-6 ○  A-15 ...
       \___/ \___/     \___/ \___/     \___/
         Even distribution across the ring
```

---

## Implementation: Virtual Nodes

```go
package consistent

import (
    "fmt"
    "hash/fnv"
    "sort"
    "strconv"
)

type VirtualNode struct {
    hash   uint32
    nodeId string  // Format: "server-id:virtual-index"
}

type HashRing struct {
    virtualNodes []VirtualNode
    virtualCount int           // Virtual nodes per physical node
    nodeMap      map[string]string  // virtual → physical mapping
}

func NewHashRing(virtualCount int) *HashRing {
    return &HashRing{
        virtualNodes: make([]VirtualNode, 0),
        virtualCount: virtualCount,
        nodeMap:      make(map[string]string),
    }
}

func hashKey(key string) uint32 {
    h := fnv.New32a()
    h.Write([]byte(key))
    return h.Sum32()
}

// Add a physical node with multiple virtual nodes
func (r *HashRing) AddNode(addr string) {
    for i := 0; i < r.virtualCount; i++ {
        virtualKey := fmt.Sprintf("%s:%d", addr, i)
        hash := hashKey(virtualKey)

        vnode := VirtualNode{
            hash:   hash,
            nodeId: virtualKey,
        }

        // Insert in sorted order
        idx := sort.Search(len(r.virtualNodes), func(i int) bool {
            return r.virtualNodes[i].hash >= hash
        })

        r.virtualNodes = append(r.virtualNodes, VirtualNode{})
        copy(r.virtualNodes[idx+1:], r.virtualNodes[idx:])
        r.virtualNodes[idx] = vnode

        // Map virtual node to physical address
        r.nodeMap[virtualKey] = addr
    }
}

// Find physical node for a key
func (r *HashRing) GetNode(key string) string {
    if len(r.virtualNodes) == 0 {
        return ""
    }

    hash := hashKey(key)

    // Find first virtual node clockwise
    idx := sort.Search(len(r.virtualNodes), func(i int) bool {
        return r.virtualNodes[i].hash >= hash
    })

    if idx == len(r.virtualNodes) {
        idx = 0  // Wrap around
    }

    virtualKey := r.virtualNodes[idx].nodeId
    return r.nodeMap[virtualKey]
}

// Remove a node (all its virtual nodes)
func (r *HashRing) RemoveNode(addr string) {
    newNodes := make([]VirtualNode, 0, len(r.virtualNodes))

    for _, vnode := range r.virtualNodes {
        // Extract physical address from virtual key
        physicalAddr := r.nodeMap[vnode.nodeId]
        if physicalAddr != addr {
            newNodes = append(newNodes, vnode)
        } else {
            delete(r.nodeMap, vnode.nodeId)
        }
    }

    r.virtualNodes = newNodes
}
```

---

## Heterogeneous Capacities

```go
// Servers with different capacities can get different virtual node counts

func (r *HashRing) AddNodeWithWeight(addr string, weight int) {
    // More weight = more virtual nodes
    virtualCount := r.virtualCount * weight

    for i := 0; i < virtualCount; i++ {
        virtualKey := fmt.Sprintf("%s:%d", addr, i)
        hash := hashKey(virtualKey)

        vnode := VirtualNode{
            hash:   hash,
            nodeId: virtualKey,
        }

        // ... insert into ring
    }
}
```

**Example:**
```
Server A (large, 16GB RAM):  weight = 2  → 200 virtual nodes
Server B (medium, 8GB RAM):   weight = 1  → 100 virtual nodes
Server C (small, 4GB RAM):    weight = 0.5 → 50 virtual nodes

Server A gets ~57% of keys (proportional to capacity)
Server B gets ~29% of keys
Server C gets ~14% of keys
```

---

## Quick Check

Before moving on, make sure you understand:

1. Why is distribution uneven without virtual nodes? (Random placement can cluster)
2. How do virtual nodes solve this? (Spread multiple points across ring)
3. How do you handle heterogeneous capacities? (Weight virtual node count)
4. What's the typical virtual node count? (100-1000 per physical node)
5. How does GetNode map from virtual to physical? (nodeId map lookup)

---

**Ready for replication? Read `step-04.md`**
