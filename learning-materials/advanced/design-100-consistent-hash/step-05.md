# Step 05: Production Concerns

---

## Hot Spot Problem

What if one key is accessed 1000x more than others?

```
Popular key: "/home" (user profile endpoint)

Hash("/home") = 12345 → Always routes to Server A

Server A: 10,000 req/sec
Server B: 100 req/sec
Server C: 100 req/sec

Server A is overwhelmed!
```

---

## Solutions for Hot Spots

### 1. Add More Virtual Nodes for Hot Keys

```go
// Detect hot keys and spread them
func (r *HashRing) AddHotSpot(key string) {
    // Create additional virtual points for this specific key
    for i := 0; i < 100; i++ {
        hotKey := fmt.Sprintf("%s:hot:%d", key, i)
        hash := hashKey(hotKey)
        // ... add to ring
    }
}

// When reading hot key, pick random replica
func (r *HashRing) GetNodeForHotSpot(key string) string {
    // Hash with random suffix
    suffix := rand.Intn(100)
    hotKey := fmt.Sprintf("%s:hot:%d", key, suffix)
    return r.GetNode(hotKey)
}
```

### 2. Replicate Hot Keys

```go
// Store hot keys on ALL servers
func (c *ReplicatedClient) WriteHotSpot(key string, value []byte) error {
    allNodes := c.getAllNodes()

    for _, node := range allNodes {
        go c.writeToNode(node, key, value)
    }

    return nil
}
```

### 3. Throttle at Load Balancer

```go
type RateLimiter struct {
    requests map[string]*rate.Limiter
    mu       sync.Mutex
}

func (rl *RateLimiter) Allow(key string) bool {
    rl.mu.Lock()
    defer rl.mu.Unlock()

    if _, exists := rl.requests[key]; !exists {
        rl.requests[key] = rate.NewLimiter(1000, 100) // 1000 req/sec
    }

    return rl.requests[key].Allow()
}
```

---

## Server Failure Detection

How do we know a server is dead?

```go
type HealthChecker struct {
    ring      *HashRing
    failures  map[string]int
    threshold int  // Mark dead after N failures
    mu        sync.Mutex
}

func (hc *HealthChecker) CheckNode(addr string) error {
    // Ping the node
    conn, err := net.DialTimeout("tcp", addr, 1*time.Second)
    if err != nil {
        hc.mu.Lock()
        hc.failures[addr]++
        failCount := hc.failures[addr]
        hc.mu.Unlock()

        if failCount >= hc.threshold {
            hc.ring.RemoveNode(addr)
            return fmt.Errorf("node %s marked dead", addr)
        }
        return err
    }
    conn.Close()

    // Reset failure count on success
    hc.mu.Lock()
    hc.failures[addr] = 0
    hc.mu.Unlock()

    return nil
}
```

---

## Graceful Server Removal

When decommissioning a server:

```go
func (c *ReplicatedClient) DecommissionNode(addr string) error {
    // 1. Mark node as "draining" (not accepting new writes)
    c.markDraining(addr)

    // 2. Wait for existing requests to finish
    time.Sleep(30 * time.Second)

    // 3. Transfer data to new replicas
    if err := c.transferData(addr); err != nil {
        return err
    }

    // 4. Remove from ring
    c.ring.RemoveNode(addr)

    return nil
}
```

---

## Monitoring and Metrics

```go
type ConsistentHashMetrics struct {
    keyDistribution map[string]int64  // node → key count
    hotKeys         map[string]int64  // key → access count
    requestLatency  map[string]time.Duration
}

func (m *ConsistentHashMetrics) RecordAccess(key, node string) {
    m.keyDistribution[node]++
    m.hotKeys[key]++
}

func (m *ConsistentHashMetrics) CheckImbalance() float64 {
    if len(m.keyDistribution) == 0 {
        return 0
    }

    var sum int64
    var max int64

    for _, count := range m.keyDistribution {
        sum += count
        if count > max {
            max = count
        }
    }

    avg := float64(sum) / float64(len(m.keyDistribution))
    imbalance := (float64(max) - avg) / avg

    return imbalance  // 0 = perfect, higher = worse
}
```

---

## Complete Production Implementation

```go
package consistent

import (
    "fmt"
    "hash/fnv"
    "sort"
    "sync"
    "time"
)

type ConsistentHash struct {
    mu            sync.RWMutex
    virtualNodes  []VirtualNode
    virtualCount  int
    nodeMap       map[string]string
    physicalNodes map[string]*PhysicalNode
}

type PhysicalNode struct {
    addr         string
    weight       int
    lastCheck    time.Time
    failures     int
    isHealthy    bool
}

func New(virtualCount int) *ConsistentHash {
    return &ConsistentHash{
        virtualNodes:  make([]VirtualNode, 0),
        virtualCount:  virtualCount,
        nodeMap:       make(map[string]string),
        physicalNodes: make(map[string]*PhysicalNode),
    }
}

func (ch *ConsistentHash) AddNode(addr string, weight int) error {
    ch.mu.Lock()
    defer ch.mu.Unlock()

    if _, exists := ch.physicalNodes[addr]; exists {
        return fmt.Errorf("node already exists")
    }

    ch.physicalNodes[addr] = &PhysicalNode{
        addr:      addr,
        weight:    weight,
        isHealthy: true,
        lastCheck: time.Now(),
    }

    virtualCount := ch.virtualCount * weight
    for i := 0; i < virtualCount; i++ {
        virtualKey := fmt.Sprintf("%s:%d", addr, i)
        hash := hashKey(virtualKey)

        vnode := VirtualNode{hash: hash, nodeId: virtualKey}

        idx := sort.Search(len(ch.virtualNodes), func(i int) bool {
            return ch.virtualNodes[i].hash >= hash
        })

        ch.virtualNodes = append(ch.virtualNodes, VirtualNode{})
        copy(ch.virtualNodes[idx+1:], ch.virtualNodes[idx:])
        ch.virtualNodes[idx] = vnode

        ch.nodeMap[virtualKey] = addr
    }

    return nil
}

func (ch *ConsistentHash) GetNode(key string) (string, error) {
    ch.mu.RLock()
    defer ch.mu.RUnlock()

    if len(ch.virtualNodes) == 0 {
        return "", fmt.Errorf("no nodes available")
    }

    hash := hashKey(key)

    idx := sort.Search(len(ch.virtualNodes), func(i int) bool {
        return ch.virtualNodes[i].hash >= hash
    })

    if idx == len(ch.virtualNodes) {
        idx = 0
    }

    // Find next healthy node
    for i := 0; i < len(ch.virtualNodes); i++ {
        actualIdx := (idx + i) % len(ch.virtualNodes)
        virtualKey := ch.virtualNodes[actualIdx].nodeId
        physicalAddr := ch.nodeMap[virtualKey]

        if node, ok := ch.physicalNodes[physicalAddr]; ok && node.isHealthy {
            return physicalAddr, nil
        }
    }

    return "", fmt.Errorf("no healthy nodes available")
}

func (ch *ConsistentHash) MarkUnhealthy(addr string) {
    ch.mu.Lock()
    defer ch.mu.Unlock()

    if node, ok := ch.physicalNodes[addr]; ok {
        node.isHealthy = false
    }
}

func (ch *ConsistentHash) MarkHealthy(addr string) {
    ch.mu.Lock()
    defer ch.mu.Unlock()

    if node, ok := ch.physicalNodes[addr]; ok {
        node.isHealthy = true
        node.failures = 0
        node.lastCheck = time.Now()
    }
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What causes hot spots? (Popular keys routing to same server)
2. How do you mitigate hot spots? (More virtual nodes, replication, throttling)
3. How do you detect dead nodes? (Health checks with failure threshold)
4. What's graceful decommissioning? (Drain, transfer, remove)
5. Why use mutex locks? (Concurrent access safety)

---

**Ready for the complete solution? Read `solution.md`**
