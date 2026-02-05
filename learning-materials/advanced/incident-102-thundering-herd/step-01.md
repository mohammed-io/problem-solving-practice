# Step 1: Understanding the Problem

---

## The Timeline

**Before restart (03:55):**
- 50,000 req/s → 47,500 cache hits (95%) + 2,500 cache misses
- Database handles 2,500 queries/sec (within capacity)

**After restart (04:00):**
- 50,000 req/s → 0 cache hits + 50,000 cache misses
- Database needs to handle 50,000 queries/sec
- Database capacity: 5,000 queries/sec
- **20x overload!**

---

## Why Not Just Add More Database Capacity?

```
Current: 5,000 queries/sec capacity
Peak need: 50,000 queries/sec
Required: 10x database capacity
```

**Problems:**
1. Expensive (10x databases)
2. Wasted most of the time (only needed during restarts)
3. Doesn't scale linearly (connection limits, locking)

**Better:** Design cache to handle restarts gracefully.

---

## The Insight

**The problem isn't cache restart itself.** The problem is that ALL requests simultaneously miss cache.

**Solution:** Spread the cache misses over time, not all at once.

---

## Quick Check

Before moving on, make sure you understand:

1. What happens during cache restart? (All requests miss simultaneously)
2. Why is adding more database capacity not ideal? (Expensive, wasted most of the time)
3. What's the core insight? (Spread cache misses over time, not all at once)
4. What's "thundering herd"? (Many requests hitting backend simultaneously)
5. Why is 95% cache hit rate not enough? (5% of 50k req/s = 2500 req/s > 5000 capacity)

---

**Continue to `step-02.md`**
