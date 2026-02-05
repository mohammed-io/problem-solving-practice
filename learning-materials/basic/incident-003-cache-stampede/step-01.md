# Step 01: Understanding the Stampede

---

## Question 1: What's Happening?

**Cache stampede in progress.**

Look at the timeline:
- 8:55 AM: Cache hit rate 95%, everything normal
- 9:00 AM: Cache hit rate drops to 5%
- 9:05 AM: Cache hit rate drops to 1%

**What changed?** The `@tech_celeb` profile was updated 30 seconds before the viral post.

**The update code:**
```javascript
await redis.del(`user:${userId}`);  // Invalidate cache
```

**The problem:** Cache was deleted but not repopulated immediately.

---

## Question 2: What Triggered This?

**Timeline:**
1. 9:00:00 - Profile updated → cache deleted
2. 9:00:30 - Viral post → millions of requests
3. 9:00:30 - All requests see cache miss
4. 9:00:30 - All requests hit database simultaneously

**Why 30 seconds?** That's how long before the viral post hit after the cache invalidation.

**The "perfect storm":**
1. Cache invalidated (update operation)
2. Traffic spike (viral post)
3. Same hot key requested by everyone
4. No cache warming

---

## Question 3: Why Isn't Cache Helping?

**Cache was deleted but empty.**

Current code:
```javascript
async function getUserProfile(userId) {
  let profile = await redis.get(`user:${userId}`);

  if (!profile) {
    // Cache miss - ALL requests hit this path!
    profile = await db.query(...);
    await redis.setex(`user:${userId}`, 3600, JSON.stringify(profile));
  }

  return JSON.parse(profile);
}
```

**What happens during stampede:**
```
Time | Request 1 | Request 2 | Request 3 | ... | Request 10,000
-----|-----------|-----------|-----------|-----|---------------
9:00:30 | GET cache: MISS | GET cache: MISS | GET cache: MISS | ... | GET cache: MISS
9:00:30 | Query DB... | Query DB... | Query DB... | ... | Query DB...
9:00:31 | SET cache | SET cache | SET cache | ... | SET cache
```

All 10,000 requests see miss, query database, and try to populate cache.

---

**What are the fix options? Read `step-02.md`**

---

## Quick Check

Before moving on, make sure you understand:

1. What is cache stampede? (Many requests miss cache simultaneously, hammer database)
2. What triggered this stampede? (Cache invalidated before viral post)
3. Why were all requests hitting the database? (Cache deleted, all requests see miss)
4. What's the "perfect storm" pattern? (Invalidation + traffic spike + same hot key)
5. Why didn't cache help during the spike? (Empty after deletion, simultaneous repopulation)

