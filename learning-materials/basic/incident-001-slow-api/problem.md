---
name: incident-001-slow-api
description: Slow API
difficulty: Basic
category: Incident Response
level: Junior to Mid-level
---
# Incident 001: Slow API

---

## The Situation

You're an engineer at E-Shop Inc. The company runs an e-commerce platform with a single API service.

**Time:** Tuesday, 10:15 AM UTC

You see a message in `#engineering`:

```
@here Store checkout is super slow right now, customers are complaining
```

You check your Grafana dashboard and see:

| Metric | Current | Normal |
|--------|---------|--------|
| Request Rate | ~500 req/s | ~500 req/s |
| p50 Latency | 450ms | 50ms |
| p95 Latency | 2800ms | 120ms |
| p99 Latency | 5000ms | 200ms |
| Error Rate | 0.1% | 0.1% |

---

## System Architecture

```
                    ┌─────────────────┐
                    │   Client Apps   │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   API Service   │
                    │   (Node.js)     │
                    │   10 instances  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   PostgreSQL    │
                    │   (RDS)         │
                    │   db.m1.large   │
                    └─────────────────┘
```

**Relevant Code (checkout endpoint):**

```javascript
app.post('/api/checkout', async (req, res) => {
  const userId = req.user.id;
  const cartItems = await db.query(
    'SELECT * FROM cart_items WHERE user_id = $1', [userId]
  );

  let total = 0;
  for (const item of cartItems.rows) {
    const product = await db.query(
      'SELECT * FROM products WHERE id = $1', [item.product_id]
    );
    total += product.rows[0].price * item.quantity;
  }

  await db.query(
    'INSERT INTO orders (user_id, total) VALUES ($1, $2)', [userId, total]
  );

  res.json({ orderId: result.rows[0].id, total });
});
```

---

## Your Task

1. **What's happening?** (Describe the symptoms in your own words)

2. **What would you check first?** (Pick a framework: RED, USE, or something else)

3. **What's the likely root cause?**

4. **What would you do right now to fix it?**

---

## Incident Response

If this were a real incident, what would you do?

**Questions to consider:**
- Is this severe enough to page someone?
- What channel would you communicate in?
- What's your first report message?

---

**When you've thought about it, read `step-01.md`**
