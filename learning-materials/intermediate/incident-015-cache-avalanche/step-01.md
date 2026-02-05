# Step 1: Analyze the Cache Expiration Pattern

---

## Hint

Look at when the cache entries were set:

```go
// All servers start at approximately the same time
Server 1: starts at 09:00:00, sets cache with TTL = 1 hour
Server 2: starts at 09:00:05, sets cache with TTL = 1 hour
Server 3: starts at 09:00:03, sets cache with TTL = 1 hour
...
Server 100: starts at 09:00:10, sets cache with TTL = 1 hour
```

**When will all these cache entries expire?**

---

## The Timeline

```
09:00:00 - Server 1 sets user:1 with TTL = 3600 seconds → expires at 10:00:00
09:00:05 - Server 2 sets user:2 with TTL = 3600 seconds → expires at 10:00:05
09:00:03 - Server 3 sets user:3 with TTL = 3600 seconds → expires at 10:00:03
...
09:00:10 - Server 100 sets user:100 with TTL = 3600 seconds → expires at 10:00:10
```

**All 10,000,000 entries expire within a 10-second window!**

---

## The Real Problem

The code used a **fixed TTL**:

```go
cache.Set(key, value, 1*time.Hour)  // Exactly 1 hour from now
```

With 100 servers starting simultaneously, their cache entries all expire around the same time.

---

**What if TTL had randomness (jitter) added?**

```go
jitter := rand.Intn(300)  // 0-300 seconds (5 minutes)
cache.Set(key, value, 1*time.Hour + time.Duration(jitter)*time.Second)
```

Now expirations are spread over 5 minutes instead of 10 seconds!

---

## Quick Check

Before moving on, make sure you understand:

1. What's a cache avalanche? (When many cache entries expire simultaneously, hammering the database)
2. What caused the synchronized expiration? (Fixed TTL without jitter, all servers started at same time)
3. What's TTL jitter? (Adding randomness to TTL so expirations are spread out)
4. Why did all entries expire in 10-second window? (100 servers started within 10 seconds, all set 1-hour TTL)
5. What's the formula for TTL with jitter? (TTL + random(0, max_jitter))

---

**Continue to `step-02.md`**
