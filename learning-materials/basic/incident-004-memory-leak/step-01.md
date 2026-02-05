# Step 01: Identifying the Memory Leak

---

## Question 1: What's the Leak Pattern?

**Memory increases steadily after each restart.**

Look at the graph:
```
Memory increases: 512MB → 1GB → OOMKilled → 512MB → 1GB → OOMKilled
```

This is a **memory leak** - memory allocated but never released.

---

## Question 2: What's Being Created Repeatedly?

Look at the new fraud detection code:

```javascript
async function checkFraud(payment) {
  const riskyUsers = await redis.get('risky_users');

  if (!riskyUsers) {
    const users = await db.query('SELECT user_id FROM risky_users WHERE active = true');
    const riskySet = new Set(users.rows.map(r => r.user_id));  // ← NEW SET
    await redis.setex('risky_users', 300, JSON.stringify([...riskySet]));
    return riskySet.has(payment.userId);
  }

  const riskySet = new Set(JSON.parse(riskyUsers));  // ← NEW SET EVERY REQUEST!
  return riskySet.has(payment.userId);
}
```

**The problem:** `new Set()` is created on **every request**!

At 100 requests/second = 100 new Sets per second = **6000 Sets per minute**.

---

## Question 3: Why Isn't GC Cleaning It Up?

**Garbage collection CAN clean up unused objects.**

But if we're creating objects faster than GC can clean them up, memory grows.

**More importantly:** Look at what happens in the cache miss path:

```javascript
if (!riskyUsers) {
    const users = await db.query(...);  // ← Holds database connection
    const riskySet = new Set(users.rows.map(r => r.user_id));
    // ... async operation ...
    await redis.setex(...);  // ← Awaiting
    // During this await, Set is still referenced
    return riskySet.has(payment.userId);
}
```

**If the query is slow** (high database load), many requests pile up, each holding a Set.

**But wait - there's a simpler issue!**

```javascript
const riskySet = new Set(JSON.parse(riskyUsers));  // ← ALWAYS RUNS
return riskySet.has(payment.userId);
```

**This path creates a new Set on every request, cache hit OR miss!**

---

## Immediate Fix

**Don't create a Set at all:**

```javascript
async function checkFraud(payment) {
  const riskyUsers = await redis.get('risky_users');

  if (!riskyUsers) {
    const users = await db.query('SELECT user_id FROM risky_users WHERE active = true');
    const riskyList = users.rows.map(r => r.user_id);
    await redis.setex('risky_users', 300, JSON.stringify(riskyList));
    return riskyList.includes(payment.userId);
  }

  // Parse once, check directly - no Set needed!
  const riskyList = JSON.parse(riskyUsers);
  return riskyList.includes(payment.userId);
}
```

**Even better - use Redis Sets:**

```javascript
async function checkFraud(payment) {
  // Use Redis SISMEMBER - O(1) operation!
  return await redis.sismember('risky_users', payment.userId);
}

// Update function (runs separately)
async function updateRiskyUsers() {
  const users = await db.query('SELECT user_id FROM risky_users WHERE active = true');
  await redis.del('risky_users');
  await redis.sadd('risky_users', users.rows.map(r => r.user_id));
  await redis.expire('risky_users', 300);
}
```

---

**For the monitoring fix, read `step-02.md`**

---

## Quick Check

Before moving on, make sure you understand:

1. What's a memory leak? (Memory allocated but never released)
2. Why was creating new Set() every request a problem? (100 req/s = 6000 Sets/min)
3. Why wasn't GC cleaning up? (Creating faster than cleanup, or held during awaits)
4. What's the simple fix? (Use Array.includes instead of Set)
5. What's the better fix? (Use Redis SISMEMBER, store in Redis as Set)

