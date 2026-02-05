# Step 02: The Hash Ring Concept

---

## The Solution: Consistent Hashing

Imagine a circle (the "ring"). Both servers and keys map to positions on this circle.

**Key assignment:** Each key is assigned to the **first server encountered clockwise** from its position.

---

## Visual: The Hash Ring

```
        0°
         |
    315° / \ 45°
        /   \
       /     \
270° ○       ○ 90°
      |       |
      |       |
240° ○       ○ 120°
       \     /
        \   /
    225° \ / 135°
         |
        180°

Servers: A (at 50°), B (at 150°), C (at 270°)
Keys: k1=80°, k2=200°, k3=300°

Assignments (clockwise):
k1 (80°)  → B (150°)  [first clockwise]
k2 (200°) → C (270°)
k3 (300°) → A (50°)   [wraps around]
```

---

## Adding a Server

```
Before: Ring has A, B, C
Add: Server D at position 100°

Only keys between 50° and 100° move to D!

k1 was at 80°:
  Before: A (50°) → k1 (80°) → B (150°) → assigned to B
  After:  A (50°) → k1 (80°) → D (100°) → assigned to D

Only ~25% of keys moved (1/4 of the ring)!
```

---

## Removing a Server

```
Remove Server B

Keys in B's range (50° to 150°) now go to C (150°)

k2 at 200°: Still assigned to C (unchanged)
k1 at 80°: Was assigned to B, now assigned to D

Only B's keys moved!
```

---

## Implementation in Go: Basic Ring

```go
package consistent

import (
    "hash/fnv"
    "sort"
)

type HashRing struct {
    nodes      []uint32  // Sorted hash positions
    addrs      []string  // Node addresses at each position
}

// Hash a string to uint32
func hashKey(key string) uint32 {
    h := fnv.New32a()
    h.Write([]byte(key))
    return h.Sum32()
}

// Add a node to the ring
func (r *HashRing) AddNode(addr string) {
    hash := hashKey(addr)

    // Find insertion point (keep sorted)
    idx := sort.Search(len(r.nodes), func(i int) bool {
        return r.nodes[i] >= hash
    })

    // Insert at idx
    r.nodes = append(r.nodes, 0)
    copy(r.nodes[idx+1:], r.nodes[idx:])
    r.nodes[idx] = hash

    r.addrs = append(r.addrs, "")
    copy(r.addrs[idx+1:], r.addrs[idx:])
    r.addrs[idx] = addr
}

// Find the node responsible for a key
func (r *HashRing) GetNode(key string) string {
    if len(r.nodes) == 0 {
        return ""
    }

    hash := hashKey(key)

    // Find first node clockwise (>= key hash)
    idx := sort.Search(len(r.nodes), func(i int) bool {
        return r.nodes[i] >= hash
    })

    // Wrap around to first node if needed
    if idx == len(r.nodes) {
        idx = 0
    }

    return r.addrs[idx]
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What is the hash ring? (Circular address space, servers and keys map to positions)
2. How are keys assigned? (First server clockwise from key position)
3. Why does adding a server only move some keys? (Only keys in the new server's range)
4. What happens when you wrap around 360°? (Continue from 0°)
5. How does GetNode use binary search? (Finds first node >= key hash)

---

**Ready to improve distribution? Read `step-03.md`**
