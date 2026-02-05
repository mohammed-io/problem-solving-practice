# Step 01: The Problem with Modulo Hashing

---

## Why Not Modulo Hashing?

```
server_index = hash(key) % N

where N = number of servers
```

**Problem:** When N changes, ALL keys remap!

---

## Visual: The Remapping Problem

```
N = 3 servers:
hash("image1.jpg") % 3 = 1 → Server 1
hash("image2.jpg") % 3 = 2 → Server 2
hash("image3.jpg") % 3 = 0 → Server 0

Add Server 4 (N = 4):
hash("image1.jpg") % 4 = 1 → Server 1 (lucky!)
hash("image2.jpg") % 4 = 3 → Server 3 (MOVED!)
hash("image3.jpg") % 4 = 1 → Server 1 (MOVED!)

Result: 2 out of 3 keys moved = 67% cache miss!
```

---

## The Impact

```
Cache cluster with 1M keys, 10 servers

Add 1 server:
→ 100% of keys remap
→ 1M cache misses
→ Database spike
→ Cascading failure

Remove 1 server:
→ 100% of keys remap
→ Same disaster
```

---

## What We Need

A hashing scheme where:
1. **Minimal data movement** when topology changes
2. **Even distribution** of keys
3. **Fast lookup** - O(log N) or better
4. **Scalable** - works with 1000s of servers

---

## Quick Check

Before moving on, make sure you understand:

1. Why does modulo hashing cause 100% remapping? (N changes, all hash values change)
2. What happens during server addition? (All keys remapped)
3. What happens during server removal? (All keys remapped)
4. Why is 100% remapping bad? (Cache misses, database spike, cascading failure)

---

**Ready for the solution? Read `step-02.md`**
