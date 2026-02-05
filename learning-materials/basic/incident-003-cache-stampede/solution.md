# Solution: Cache Stampede

---

## Root Cause

**Cache invalidation before repopulation** caused a stampede.

### The Sequence

1. **8:59:30** - Profile update runs `redis.del(user:tech_celeb)`
2. **8:59:31** - Cache is now empty
3. **9:00:00** - Viral post goes live, thousands of requests per second
4. **9:00:00** - Every request sees cache miss, hits database
5. **9:00:00** - Each request tries to repopulate cache after DB fetch
6. **9:00:01** - Database is overwhelmed, 5000+ identical queries

The cache provided **zero protection** because:
- The hot key was invalidated
- It wasn't repopulated before the traffic hit
- All requests saw "miss" simultaneously

---

## The Fix

### Immediate Fix (Cache Warming)

```javascript
// After invalidating, IMMEDIATELY repopulate
async function updateProfile(userId, newData) {
  // Update database
  await db.query(
    'UPDATE profiles SET ... WHERE user_id = $1', [userId, newData]
  );

  // Invalidate OLD cache
  await redis.del(`user:${userId}`);

  // IMMEDIATELY repopulate with NEW data
  const freshData = await db.query(
    'SELECT * FROM profiles WHERE user_id = $1', [userId]
  );
  await redis.setex(`user:${userId}`, 3600, JSON.stringify(freshData));
}
```

### Better Fix: Cache-Aside with Lock

```javascript
async function getUserProfile(userId) {
  // Try cache first
  let profile = await redis.get(`user:${userId}`);
  if (profile) {
    return JSON.parse(profile);
  }

  // Cache miss - use lock to prevent stampede
  const lockKey = `lock:user:${userId}`;
  const lock = await redis.set(lockKey, '1', 'NX', 'EX', 5); // 5 second lock

  if (lock) {
    // We got the lock - WE do the DB fetch
    console.log(`Cache miss for user:${userId} - we're rebuilding`);
    const profile = await db.query(
      'SELECT * FROM profiles WHERE user_id = $1', [userId]
    );

    // Cache for 1 hour with random jitter
    const ttl = 3600 + Math.random() * 60; // Avoids synchronized expiration
    await redis.setex(`user:${userId}`, ttl, JSON.stringify(profile.rows[0]));

    await redis.del(lockKey); // Release lock
    return profile.rows[0];
  } else {
    // Someone else is rebuilding - wait and retry
    await sleep(50); // 50ms
    return getUserProfile(userId); // Retry
  }
}
```

### Best Fix: Probabilistic Early Refresh

```javascript
// Refresh cache BEFORE it expires
async function getUserProfile(userId) {
  const profile = await redis.get(`user:${userId}`);

  if (profile) {
    const data = JSON.parse(profile);
    const ttl = await redis.ttl(`user:${userId}`);

    // If TTL < 60 seconds, refresh asynchronously
    if (ttl < 60) {
      // Don't wait - fire and forget
      refreshCacheInBackground(userId);
    }

    return data;
  }

  // Cache miss - fetch from DB
  return fetchAndCache(userId);
}
```

---

## Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| **Invalidate + Repopulate** | Simple, no stampede | Update path is slower |
| **Lock (Redlock)** | Prevents stampede | More complex, lock contention |
| **Probabilistic Refresh** | Hot keys always cached | Background traffic, stale-ish data |
| **Always Cache** | Never stampede | Can serve stale data |
| **Shard Hot Keys** | Distributes load | More keys to manage |

For social media profiles: **Probabilistic Early Refresh** is ideal - users rarely notice 60-second staleness, and you avoid stampedes entirely.

---

## Systemic Prevention (Staff Level)

### 1. Detect Hot Keys

```javascript
// Track request frequency per key
const keyCounts = new Map();
setInterval(() => {
  for (const [key, count] of keyCounts) {
    if (count > 1000) {
      console.warn(`Hot key detected: ${key} (${count}/min)`);
      // Auto-enable sharding or longer TTL
    }
  }
  keyCounts.clear();
}, 60000);
```

### 2. Cache Jitter

Always add random jitter to TTL:

```javascript
// BAD: Everything expires at once
await redis.setex(key, 3600, value);  // Everything in 1 hour

// GOOD: Stagger expiration
const ttl = 3600 + Math.floor(Math.random() * 300);  // ±2.5 minutes
await redis.setex(key, ttl, value);
```

### 3. Cache Hierarchy

```
┌─────────────────────────────────────────┐
│         L1: In-memory cache              │  (5 second TTL)
│         (per-instance, fastest)          │
└────────────┬────────────────────────────┘
             │ miss
             ▼
┌─────────────────────────────────────────┐
│         L2: Redis                       │  (1 hour TTL)
│         (distributed, medium)            │
└────────────┬────────────────────────────┘
             │ miss
             ▼
┌─────────────────────────────────────────┐
│         L3: Database                    │  (persistent)
│         (slowest)                        │
└─────────────────────────────────────────┘
```

L1 cache absorbs short-term spikes. Even if Redis is invalidated, L1 still has data.

---

## Real Incident

**Facebook (2011)**: A cache stampede on a single hot key caused their entire memcached infrastructure to fail. The fix: implement "lease" mechanism (similar to locks) and probabilistic expiration.

---

## Jargon

| Term | Definition |
|------|------------|
| **Cache stampede** | Many requests simultaneously miss cache and hit backend |
| **Hot key** | Cache key receiving disproportionately high traffic |
| **Cache warming** | Pre-populating cache before it's needed |
| **TTL jitter** | Adding randomness to expiration time to avoid synchronized expiration |
| **Lock contention** | Multiple processes competing for the same lock |
| **Lease mechanism** | Cache pattern where only one process can rebuild a value |
| **Cache hierarchy** | Multiple cache layers (L1, L2, L3) with different speed/cost |
| **Fire and forget** | Asynchronous operation where sender doesn't wait for result |

---

## What As a Staff Engineer

You should recognize:

1. **Cache invalidation is dangerous** - Think about what happens if traffic spikes right after

2. **Hot keys exist** - They're not failures, they're expected. Design for them.

3. **Monitoring matters** - You should alert on:
   - Sudden drop in cache hit rate
   - Single key receiving >1000 req/s
   - Database load spike correlating with cache miss pattern

4. **Architecture decision** - For your use case, pick the right cache strategy:
   - Social profiles: Probabilistic refresh is fine (users accept slight staleness)
   - Inventory/stock: Must be accurate, need different approach
   - Payments: Never use cache for source of truth

---

**Next Problem:** `basic/incident-004-memory-leak/`
