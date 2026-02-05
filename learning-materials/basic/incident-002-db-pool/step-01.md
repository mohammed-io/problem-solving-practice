# Step 01

---

## Do The Math

First, understand your connection requirements:

```
Total connections needed = (pods × workers per pod × pool size) + background
```

**Before the deploy (what was planned):**
- 20 pods × 4 workers × 10 connections = **800 connections requested**
- But DB max is only **500**!

---

## Wait, That Doesn't Add Up

If the system was requesting 800 connections but DB max is 500...
**Why was it working before the deploy?**

Things to consider:
1. Connection pools don't create all connections upfront
2. They create connections **on demand** (lazy initialization)
3. Maybe not all workers were using all their pool slots?

---

## What Changed With the Deploy?

The new code added a **background job** that:
- Runs every 30 seconds
- Needs a database connection to query payments
- But where does it run? In the same pods? Separate service?

---

## Key Question

**Does the background job create its own connection pool, or does it share the existing one?**

If it creates its own pool of 10 connections... and there are 20 pods...

```
Additional connections = 20 pods × 10 connections = 200 connections
```

**That would push the total from 800 to 1000 requested!**

But wait - the DB is at max (500). How is this even possible?

---

**Still confused? Read `step-02.md`**

---

## Quick Check

Before moving on, make sure you understand:

1. What's the connection math? (pods × workers × pool_size = total needed)
2. Why was it working before the deploy? (Pools lazy-initialize, weren't at max capacity)
3. What happens when requested > max? (Connections wait, timeout, or fail)
4. How many connections did background job add? (20 pods × 10 = 200 connections)
5. Why does connection wait time matter? (850ms wait means pool exhausted)
