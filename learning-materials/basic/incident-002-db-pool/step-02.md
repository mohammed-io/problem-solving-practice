# Step 02

---

## Connection Pools Are Lazy (Mostly)

Here's what's happening:

1. **Normal operation**: Each pod creates connections **as needed**
   - 4 workers per pod, pool size 10
   - But under normal load, each worker might only use 2-3 connections
   - Actual usage: 20 pods × 4 workers × 3 connections = ~240 connections

2. **Under load**: Workers need more connections
   - Pool grows from 3 → 10 per worker
   - Actual usage: 20 pods × 4 workers × 10 connections = **800 connections**
   - But DB max is 500!
   - So connections wait (timeout) or fail

---

## What the Deploy Changed

The new background job code:

```javascript
// NEW CODE - runs in each pod
setInterval(async () => {
  // Opens a NEW connection pool!
  const pool = new Pool({
    host: process.env.DB_HOST,
    max: 10  // Its own pool!
  });

  const payments = await pool.query('SELECT * FROM payments WHERE synced = false');
  // ... sync to warehouse ...

  await pool.end();  // But does this actually get called?
}, 30000);
```

---

## The Problem

1. Each pod now has **two** connection pools:
   - The main request handler pool (10 connections)
   - The background job pool (10 connections)

2. The background job creates connections **every 30 seconds**
3. The `pool.end()` might not be called reliably (error handling?)

4. Result: Connections are **leaking** - created but not properly closed

---

## The Smoking Gun

Look at the connection wait time: **850ms**

This means:
- Application is asking for a connection
- Pool says "all 10 are busy, wait"
- Application waits 850ms
- Times out

---

**Want to see the fix and deeper analysis? Read `solution.md`**

---

## Quick Check

Before moving on, make sure you understand:

1. Why do connection pools use lazy initialization? (Don't create all connections upfront)
2. What did the deploy change? (Added new pool per pod, connections leaking)
3. What's a connection leak? (Connections created but not properly closed)
4. Why does connection wait time indicate pool exhaustion? (850ms wait = all connections busy)
5. What's the fix? (Share existing pool, properly close connections, use single pool)

