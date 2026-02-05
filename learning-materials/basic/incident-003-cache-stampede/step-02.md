# Step 02: Fixing Cache Stampede

---

## Question 4: Fix Options

### Immediate Fix: Rate Limiting

```javascript
// Quick: Add rate limiting per IP
const rateLimit = new Map();

async function getUserProfile(userId, clientIp) {
  const key = `ratelimit:${clientIp}`;
  const count = rateLimit.get(key) || 0;

  if (count > 10) {
    throw new Error('Too many requests');
  }

  rateLimit.set(key, count + 1);
  setTimeout(() => rateLimit.delete(key), 60000); // Clear after 1 min

  // ... rest of function
}
```

---

### Better Fix: Lock Cache (Prevents Duplicate Work)

```javascript
async function getUserProfile(userId) {
  let profile = await redis.get(`user:${userId}`);

  if (!profile) {
    const lockKey = `lock:user:${userId}`;

    // Try to acquire lock (only one request does DB query)
    const lock = await redis.set(lockKey, '1', 'NX', 'EX', 10);

    if (lock) {
      // We got the lock - fetch from DB
      console.log(`Cache miss for user:${userId} - I'll fetch!`);
      profile = await db.query(
        'SELECT * FROM profiles WHERE user_id = $1', [userId]
      );
      await redis.setex(`user:${userId}`, 3600, JSON.stringify(profile));
      await redis.del(lockKey); // Release lock
    } else {
      // Lock held - wait briefly and retry
      await sleep(50); // 50ms
      profile = await redis.get(`user:${userId}`);

      // Still not there? Fetch anyway (fallback)
      if (!profile) {
        profile = await db.query('SELECT * FROM profiles WHERE user_id = $1', [userId]);
      }
    }
  }

  return JSON.parse(profile);
}
```

---

### Best Fix: Request Coalescing (Single Flight)

```javascript
// Use single-flight pattern
const inflight = new Map();

async function getUserProfile(userId) {
  // Check cache first
  let profile = await redis.get(`user:${userId}`);
  if (profile) return JSON.parse(profile);

  // Check if request is in-flight
  if (inflight.has(userId)) {
    console.log(`Waiting for in-flight request for ${userId}`);
    return await inflight.get(userId); // Wait for same request
  }

  // Create the promise and store it
  const promise = (async () => {
    profile = await db.query('SELECT * FROM profiles WHERE user_id = $1', [userId]);
    await redis.setex(`user:${userId}`, 3600, JSON.stringify(profile));
    inflight.delete(userId); // Clear in-flight
    return profile;
  })();

  inflight.set(userId, promise);
  return await promise;
}
```

---

### Preventive Fix: Cache Warming

```javascript
// Before cache expires, refresh it
async function warmCache(userId) {
  const profile = await db.query('SELECT * FROM profiles WHERE user_id = $1', [userId]);
  await redis.setex(`user:${userId}`, 3600, JSON.stringify(profile));
}

// Run this periodically
async function cacheWarmer() {
  // Find keys expiring in next 5 minutes
  const keys = await redis.keys('user:*');

  for (const key of keys) {
    const ttl = await redis.ttl(key);
    if (ttl > 0 && ttl < 300) { // Expiring within 5 minutes
      const userId = key.split(':')[1];
      await warmCache(userId);
    }
  }
}

setInterval(cacheWarmer, 60000); // Every minute
```

---

### Another Fix: Probabilistic Expiration

```javascript
// Add jitter to TTL to spread out expirations
function getTTL(baseTTL) {
  // Add ±10% random jitter
  const jitter = Math.random() * (baseTTL * 0.2) - (baseTTL * 0.1);
  return baseTTL + jitter;
}

await redis.setex(`user:${userId}`, getTTL(3600), JSON.stringify(profile));
```

---

## Question 5: Staff Level Prevention

**1. Monitoring:**
- Alert on cache hit rate dropping below 80%
- Alert on "cache miss storm" (many misses for same key)
- Alert on database connection pool exhaustion

**2. Circuit breakers:**
- If database is overloaded, fail fast
- Return stale data or error message
- Don't queue infinite requests

**3. Hot key protection:**
- Detect hot keys (high request rate)
- Automatically increase TTL for hot keys
- Pre-warm hot keys before expiration

**4. Load shedding:**
- During overload, shed low-priority traffic
- Return cached data even if stale
- Degrade gracefully

---

**Now read `solution.md` for complete reference implementation.**

---

## Quick Check

Before moving on, make sure you understand:

1. What's request coalescing (singleflight)? (Multiple requests share same in-flight fetch)
2. How does cache locking prevent stampede? (Only one request fetches, others wait)
3. What's cache warming? (Refresh before expiry to prevent simultaneous miss)
4. What's probabilistic expiration? (Add jitter to TTL to spread out expirations)
5. What's hot key protection? (Detect high-traffic keys, increase TTL, pre-warm)

