# Step 1: Sharding Strategy Comparison

---

## Compare Sharding Approaches

### Hash-based Sharding

```go
func getShard(key string, numShards int) int {
    hash := sha256.Sum256([]byte(key))
    return int(binary.BigEndian.Uint64(hash[:8]) % uint64(numShards))
}
```

**Pros:**
- Even distribution (assuming good hash)
- Simple to implement
- No hot spots (assuming keys uniform)

**Cons:**
- Rebalancing requires moving ALL data
- Can't do range queries efficiently
- Adding shards = massive data movement

### Range-based Sharding

```go
func getShard(key string, ranges []Range) int {
    // ranges = [{start: "a", end: "f", shard: 0}, ...]
    for _, r := range ranges {
        if key >= r.Start && key < r.End {
            return r.Shard
        }
    }
    return 0  // default
}
```

**Pros:**
- Range queries efficient (all data in one shard)
- Can optimize for known access patterns
- Partial rebalancing possible

**Cons:**
- Hot spots if keys not uniform
- Complex to manage ranges
- Can become imbalanced

### Consistent Hashing

```
       Node C
      /    \
     /      \
Node A       Node E
 |             |
Node B       Node D
```

Each node gets multiple points on hash ring. Key hashes to position; nearest node (clockwise) owns it.

**Pros:**
- Adding/removing nodes = minimal data movement
- Natural load balancing
- Handles heterogenous node capacities

**Cons:**
- More complex to implement
- Still need to handle hot keys
- Virtual nodes add overhead

---

## Which would you choose?

For a KV store where:
- Access patterns unknown (could be anything)
- Need to add/remove capacity dynamically
- Want minimal disruption during scaling

**Consistent hashing is usually the best choice.**

---

## Quick Check

Before moving on, make sure you understand:

1. What's the main drawback of hash-based sharding? (Rebalancing requires moving ALL data)
2. What's the main benefit of range-based sharding? (Range queries are efficient)
3. What's consistent hashing? (Hash ring where each node has multiple points)
4. Why does consistent hashing minimize data movement? (Adding/removing node affects only its neighbors)
5. When would you choose range-based over consistent hashing? (When you need efficient range queries)

---

**Continue to `step-02.md`**
