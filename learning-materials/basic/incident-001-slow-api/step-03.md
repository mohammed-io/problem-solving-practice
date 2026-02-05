# Step 03

---

## The Pattern

This is the **N+1 Query Problem**:

- **1** query to get the cart items
- **N** additional queries to get product details (one per item)
- Plus **1** final insert query

Total queries: `1 + N + 1 = N + 2`

For a cart with 10 items: **12 database round-trips**

---

## Why This Is Slow

Each database query has:
- **Network latency** (even on same network: ~1-5ms)
- **Query planning** (Postgres figures out how to execute)
- **Execution** (actual data retrieval)

For 10 items, if each query takes 10ms: **100ms just for product lookups**

For 50 items (big shopping cart): **500ms**

---

## The Real Problem

This code has probably worked fine for months. Why slow now?

**Think about the business context:**

- It's approaching the holidays
- More customers = larger carts
- Some customers are adding 20-50 items to cart

The code was **always inefficient**, but it became visible as carts grew.

---

## What To Check

Before you fix it, **verify your hypothesis**:

1. Look at the database logs - are there more queries than expected?
2. Check application logs - is query latency elevated?
3. Add timing to the code - where is the time spent?

---

**Want to see the fix? Read `solution.md`**
