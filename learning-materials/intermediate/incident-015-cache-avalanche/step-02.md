# Step 2: Understand the Solution

---

## Root Cause

**Fixed TTL without jitter** caused synchronized cache expiration:

```
Cache warming at 09:00 → All entries expire at 10:00 ± 10 seconds
→ Database hammered with 19x normal load
```

---

## The Solutions

### Solution 1: Add Jitter to TTL

```go
// Add random jitter (±10% of TTL)
ttl := 1 * time.Hour
jitter := time.Duration(rand.Int63n(int64(ttl) / 10))  // 0-6 minutes

cache.Set(key, value, ttl+jitter)
```

Now expirations spread over 6+ minutes instead of seconds.

### Solution 2: Exponential TTL

```go
// Different user types have different TTLs
func getTTL(user User) time.Duration {
    switch {
    case user.Followers > 1000000:
        return 2 * time.Hour  // Celebrities cache longer
    case user.Followers > 10000:
        return 1 * time.Hour  // Popular users
    default:
        return 30 * time.Minute  // Normal users
    }
}
```

### Solution 3: Probabilistic Early Expiration

```go
// Randomly expire 5% of cache early to smooth load
if rand.Float64() < 0.05 {
    cache.Set(key, value, ttl/2)  // Expire early
} else {
    cache.Set(key, value, ttl)
}
```

---

## Questions

1. **Which solution is best?** (Think about complexity vs effectiveness)

2. **What if you still want cache warming?** (Can it be done safely?)

3. **How do you monitor for potential avalanches?**

---

## Quick Check

Before moving on, make sure you understand:

1. What's the simplest solution? (Add jitter to TTL - spread out expirations randomly)
2. What's exponential TTL? (Different data types have different TTLs based on access patterns)
3. What's probabilistic early expiration? (Randomly expire small percentage early to smooth load)
4. Which solution is best? (Jitter is simplest and most effective)
5. What's the trade-off with cache warming? (Avoid warming all at once, or add jitter)

---

**When you've considered these, read `solution.md`**
