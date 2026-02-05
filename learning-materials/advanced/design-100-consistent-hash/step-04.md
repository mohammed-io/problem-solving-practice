# Step 04: Replication for Redundancy

---

## Why Replicate?

A single server failure = data loss. We need **replication**.

```
Server holding your data fails:
→ Data lost
→ Cache miss
→ Database spike

With replication:
→ Data exists on multiple servers
→ Survive single (or more) failures
```

---

## Replication on the Hash Ring

Store each key on **N consecutive servers** clockwise.

```
Replication factor: 3

Key "image.jpg" hashes to position 150:

Primary:   Server A (first clockwise)
Replica 1: Server B (second clockwise)
Replica 2: Server C (third clockwise)

If Server A fails:
→ Check Server B (has replica)
→ If Server B also fails, check Server C
```

---

## Visual: Replicated Ring

```
Ring with replication factor = 3

Key K at position 200°:

        K (200°)
         |
         v
    ○ A (250°) ── Primary
    ○ B (300°) ── Replica 1
    ○ C (10°)  ── Replica 2  (wrapped)

If A fails: B becomes primary
If A and B fail: C becomes primary
```

---

## Implementation: Replicated Get

```go
// Get N unique physical nodes for a key
func (r *HashRing) GetNodes(key string, count int) []string {
    if len(r.virtualNodes) == 0 {
        return nil
    }

    hash := hashKey(key)

    // Find starting position
    idx := sort.Search(len(r.virtualNodes), func(i int) bool {
        return r.virtualNodes[i].hash >= hash
    })

    if idx == len(r.virtualNodes) {
        idx = 0  // Wrap around
    }

    result := make([]string, 0, count)
    seen := make(map[string]bool)

    // Collect 'count' unique physical nodes
    for i := 0; i < len(r.virtualNodes) && len(result) < count; i++ {
        actualIdx := (idx + i) % len(r.virtualNodes)
        virtualKey := r.virtualNodes[actualIdx].nodeId
        physicalAddr := r.nodeMap[virtualKey]

        if !seen[physicalAddr] {
            seen[physicalAddr] = true
            result = append(result, physicalAddr)
        }
    }

    return result
}

// Usage: Get replicas for a key
func (r *HashRing) GetReplicas(key string, replicationFactor int) ([]string, string) {
    nodes := r.GetNodes(key, replicationFactor)

    if len(nodes) == 0 {
        return nil, ""
    }

    // First node is primary
    primary := nodes[0]

    // Rest are replicas
    replicas := nodes[1:]

    return replicas, primary
}
```

---

## Write Path: Writing to Replicas

```go
type ReplicatedClient struct {
    ring *HashRing
    rf   int  // Replication factor
}

func (c *ReplicatedClient) Write(key string, value []byte) error {
    nodes := c.ring.GetNodes(key, c.rf)

    if len(nodes) < c.rf {
        return fmt.Errorf("not enough nodes available")
    }

    // Write to all replicas
    errors := make(chan error, len(nodes))

    for _, nodeAddr := range nodes {
        go func(addr string) {
            errors <- c.writeToNode(addr, key, value)
        }(nodeAddr)
    }

    // Wait for all writes
    for i := 0; i < len(nodes); i++ {
        if err := <-errors; err != nil {
            // Log error, continue
            // In production: retry or mark node dead
        }
    }

    return nil
}

func (c *ReplicatedClient) writeToNode(addr, key string, value []byte) error {
    // Actual network call to node
    return nil
}
```

---

## Read Path: Read with Fallback

```go
func (c *ReplicatedClient) Read(key string) ([]byte, error) {
    nodes := c.ring.GetNodes(key, c.rf)

    // Try primary first
    for _, nodeAddr := range nodes {
        data, err := c.readFromNode(nodeAddr, key)
        if err == nil {
            return data, nil  // Success
        }
        // Try next replica
    }

    return nil, fmt.Errorf("all replicas failed")
}

func (c *ReplicatedClient) readFromNode(addr, key string) ([]byte, error) {
    // Actual network call to node
    return nil, nil
}
```

---

## Replication Factor Trade-offs

| RF | Pros | Cons |
|----|------|------|
| **1** | Fast, minimal storage | No redundancy |
| **2** | Survive 1 failure | Still risky |
| **3** | Industry standard | 3x storage, 3x write latency |
| **5+** | Very durable | High cost, slow writes |

**Recommendation:** RF = 3 for most use cases.

---

## Quorum Reads and Writes

Don't need all replicas to respond!

```
N = replication factor = 3
W = write quorum = 2  (wait for 2 replicas)
R = read quorum = 2    (read from 2 replicas)

Rule: R + W > N
      2 + 2 > 3 ✓ Guarantees latest read

Consistent if: R + W > N
Fastest if: R = 1, W = N (or vice versa)
```

---

## Quick Check

Before moving on, make sure you understand:

1. Why do we need replication? (Survive failures, data redundancy)
2. How are replicas chosen? (Next N nodes clockwise)
3. What happens if primary fails? (Next replica becomes primary)
4. What's the typical replication factor? (3 for most systems)
5. What's the quorum rule? (R + W > N for consistency)

---

**Ready for production concerns? Read `step-05.md`**
