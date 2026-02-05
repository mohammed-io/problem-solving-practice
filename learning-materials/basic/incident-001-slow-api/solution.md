# Solution: N+1 Query Problem

---

## Root Cause

**N+1 Query Pattern** - Making N additional queries inside a loop.

The checkout endpoint makes one query to get cart items, then loops through them making a separate query for each product's details.

For a cart with 50 items: **51 database queries** instead of 2.

---

## The Fix

### Immediate Fix (Code)

```javascript
app.post('/api/checkout', async (req, res) => {
  const userId = req.user.id;

  // Get cart items
  const cartItems = await db.query(
    'SELECT * FROM cart_items WHERE user_id = $1', [userId]
  );

  // Get ALL product details in ONE query
  const productIds = cartItems.rows.map(item => item.product_id);
  const products = await db.query(
    'SELECT * FROM products WHERE id = ANY($1)', [productIds]
  );

  // Build lookup map
  const productMap = new Map(
    products.rows.map(p => [p.id, p])
  );

  // Calculate total (no DB queries!)
  let total = 0;
  for (const item of cartItems.rows) {
    const product = productMap.get(item.product_id);
    total += product.price * item.quantity;
  }

  await db.query(
    'INSERT INTO orders (user_id, total) VALUES ($1, $2)', [userId, total]
  );

  res.json({ orderId: result.rows[0].id, total });
});
```

**Before:** 1 + N + 1 queries
**After:** 2 queries (always!)

### Immediate Fix (Hot Patch)

If you can't deploy code immediately:

```javascript
// Quick mitigation: cache product lookups
const productCache = new Map();

async function getProduct(productId) {
  if (productCache.has(productId)) {
    return productCache.get(productId);
  }
  const product = await db.query(
    'SELECT * FROM products WHERE id = $1', [productId]
  );
  productCache.set(productId, product.rows[0]);
  return product.rows[0];
}
```

This is **not a real fix** but can reduce load while deploying.

---

## Why This Happened

| Factor | Contributed To |
|--------|----------------|
| Developer unfamiliar with N+1 pattern | Didn't recognize the anti-pattern |
| No code review feedback | Problem wasn't caught |
| No query performance monitoring | Issue wasn't visible until users complained |
| Business growth (larger carts) | Hidden issue became visible |

---

## Prevention

### 1. Code Review Checklist

Add to your team's code review template:

```markdown
## Database Query Review
- [ ] No queries in loops
- [ ] Using JOIN or WHERE IN / ANY for multiple lookups
- [ ] EXPLAIN ANALYZE run for queries
```

### 2. Monitoring

Add a metric for "queries per request":

```javascript
const queryCount = new Map();

function trackQuery(operation) {
  const count = queryCount.get(operation) || 0;
  queryCount.set(operation, count + 1);
}

// Log per-request query count
app.use((req, res, next) => {
  queryCount.clear();
  next();

  res.on('finish', () => {
    const total = [...queryCount.values()].reduce((a, b) => a + b, 0);
    if (total > 10) {
      console.warn(`High query count: ${total} for ${req.path}`);
    }
  });
});
```

### 3. Database Connection Pool Monitoring

Alert when:
- Average query time increases
- Queries per second spikes
- Connection pool nears capacity

---

## The Real Incident

This exact pattern caused issues at:
- **GitHub** (2016): N+1 queries caused slow page loads
- **Shopify** (2018): Black Friday exposed N+1 in cart
- **Stripe** (2020): API slowdown from N+1 in dashboard

---

## Trade-offs Discussed

| Approach | Pros | Cons |
|----------|------|------|
| **JOIN** | One query, automatic optimization | Complex query, can't cache products separately |
| **WHERE IN / ANY** | Simple, leverages DB index | Need to build array of IDs |
| **DataLoader** (Facebook) | Batches queries automatically | More complex, requires framework |
| **Application cache** | Reduces DB load | Cache invalidation complexity |

For this case: **WHERE IN / ANY** is the sweet spot - simple and effective.

---

## Jargon

| Term | Definition |
|------|------------|
| **N+1 Query** | One query to fetch N items, then N queries to fetch related data (anti-pattern) |
| **Round-trip** | Network request to database and response back - has latency cost |
| **Query planning** | PostgreSQL's process of deciding how to execute a query (which index to use, join order, etc.) |
| **Hot patch** | Quick fix deployed urgently, often not the ideal long-term solution |
| **WHERE IN / ANY** | SQL pattern to fetch multiple rows in a single query using an array of values |

---

## Incident Report (For Practice)

```markdown
## Incident: Checkout API Latency

**Severity:** P2 (degraded performance)
**Time Started:** 2024-11-26 10:15 UTC
**Time Resolved:** 2024-11-26 11:30 UTC
**Duration:** 1 hour 15 minutes

### Impact
- Checkout API p95 latency increased from 120ms to 2800ms
- Customers experiencing slow checkout process
- No errors, but degraded user experience

### Root Cause
N+1 query pattern in checkout endpoint - making one DB query per cart item.

### Resolution
- Refactored to use WHERE IN / ANY pattern
- Reduced from 50+ queries to 2 queries per request
- Deployed hotfix at 11:30 UTC

### Follow-up Actions
- [ ] Add query count monitoring per endpoint
- [ ] Add N+1 detection to code review checklist
- [ ] Implement query performance dashboard
- [ ] Team training on database query patterns
```

---

## What Would You Do Differently?

1. **When would you page on-call?** (P0 vs P1 vs P2)
   - This was P2: degraded but functional
   - Would you page at p95 = 1000ms? 2000ms?

2. **How would you communicate this?**
   - Public status page?
   - Customer notification?
   - Internal only?

3. **What monitoring would have caught this earlier?**

---

**Next Problem:** `basic/incident-002-db-connection-pool/`
