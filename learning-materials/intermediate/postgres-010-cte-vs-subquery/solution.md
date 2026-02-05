# Solution: CTE vs Subquery - Materialization Overhead

---

## Root Cause

**PostgreSQL < 12 materializes all CTEs** (optimization fence), causing:
1. Each CTE fully computed and stored
2. InitPlans re-scan materialized CTEs
3. Multiple table scans for same data

Your query scans `orders` table 3 times (once per CTE), then re-scans the results.

---

## The Fix

### Option 1: Convert to Subqueries (PostgreSQL < 12)

```sql
SELECT
    (SELECT JSON_AGG(json_build_object('month', month, 'sales', sales_total, 'orders', order_count))
     FROM (
         SELECT
             DATE_TRUNC('month', order_date) AS month,
             SUM(total_amount) AS sales_total,
             COUNT(*) AS order_count
         FROM orders
         WHERE order_date >= NOW() - INTERVAL '12 months'
         GROUP BY DATE_TRUNC('month', order_date)
     ) AS monthly_sales) AS monthly_trend,

    (SELECT JSON_AGG(json_build_object('product', name, 'sold', total_sold))
     FROM (
         SELECT
             p.name,
             SUM(oi.quantity) AS total_sold
         FROM order_items oi
         JOIN products p ON p.product_id = oi.product_id
         JOIN orders o ON o.order_id = oi.order_id
         WHERE o.order_date >= NOW() - INTERVAL '12 months'
         GROUP BY p.product_id, p.name
         ORDER BY total_sold DESC
         LIMIT 10
     ) AS top_products) AS top_products,

    (SELECT JSON_AGG(json_build_object('region', region_name, 'sales', regional_sales))
     FROM (
         SELECT
             r.region_name,
             SUM(o.total_amount) AS regional_sales
         FROM orders o
         JOIN users u ON u.user_id = o.user_id
         JOIN regions r ON r.region_id = u.region_id
         WHERE o.order_date >= NOW() - INTERVAL '12 months'
         GROUP BY r.region_name
     ) AS regional_performance) AS regional_performance;
```

**Result:** PostgreSQL can inline and optimize each subquery independently.

### Option 2: Add Indexes (works with both CTE and subquery)

```sql
-- For monthly_sales aggregation
CREATE INDEX idx_orders_date ON orders(order_date DESC)
    INCLUDE (total_amount);

-- For top_products
CREATE INDEX idx_order_items_product ON order_items(product_id, quantity);
CREATE INDEX idx_orders_date_id ON orders(order_date, order_id);

-- For regional_performance
CREATE INDEX idx_orders_user_date ON orders(user_id, order_date)
    INCLUDE (total_amount);
CREATE INDEX idx_users_region ON users(region_id, user_id);
```

### Option 3: Use MATERIALIZED View (for repeated queries)

```sql
CREATE MATERIALIZED VIEW dashboard_metrics AS
SELECT
    DATE_TRUNC('month', order_date) AS month,
    SUM(total_amount) AS sales_total,
    COUNT(*) AS order_count,
    -- ... other aggregations
FROM orders
WHERE order_date >= NOW() - INTERVAL '12 months'
GROUP BY DATE_TRUNC('month', order_date);

-- Refresh periodically (cron job)
REFRESH MATERIALIZED VIEW CONCURRENTLY dashboard_metrics;
```

### Option 4: Upgrade PostgreSQL (12+)

PostgreSQL 12+ automatically inlines CTEs:

```sql
-- Now this is optimized (auto-inlined)
WITH monthly_sales AS (
    SELECT DATE_TRUNC('month', order_date) AS month, ...
    FROM orders
    WHERE order_date >= NOW() - INTERVAL '12 months'
    GROUP BY 1
)
SELECT * FROM monthly_sales;

-- If you NEED materialization (rare):
WITH monthly_sales AS MATERIALIZED (
    SELECT ...
)
SELECT * FROM monthly_sales;
```

---

## Performance Comparison

| Approach | Execution Time | PostgreSQL < 12 | PostgreSQL 12+ |
|----------|----------------|------------------|----------------|
| CTE (original) | 8-12s | Materialized (slow) | Inlined (fast) |
| Subquery | 2-3s | Inlined (fast) | Inlined (fast) |
| With indexes | 0.5-1s | Much faster | Much faster |
| Materialized view | 0.01s | Instant (but stale) | Instant (but stale) |

---

## When to Use CTEs

**Good for CTEs:**
- Recursive queries (hierarchies, graphs)
- Breaking complex query into readable parts (PostgreSQL 12+)
- When you NEED materialization (PostgreSQL 12+ with `MATERIALIZED`)
- Data transformation pipelines

**Good for Subqueries:**
- Simple filtering/aggregation
- When optimization matters (PostgreSQL < 12)
- Single-use derived tables

**Good for LATERAL:**
- Correlated subqueries in FROM clause
- Complex calculations per row
- Avoiding repeated subqueries

---

## PostgreSQL Version Differences

| Feature | PostgreSQL < 12 | PostgreSQL 12+ |
|---------|-----------------|----------------|
| CTE execution | Always materialized | Auto-inlined (optimization) |
| `MATERIALIZED` keyword | Not available | Force materialization |
| CTE performance | Often slower | Same as subquery |
| Query optimization | Blocked at CTE boundary | Can optimize across CTE |

---

## Monitoring

```sql
-- Check PostgreSQL version
SELECT version();

-- Check if CTEs are being materialized
EXPLAIN (ANALYZE, BUFFERS) WITH your_cte AS (...)
SELECT * FROM your_cte;

-- Look for "CTE Scan" vs inline operations
```

---

## Best Practices

### For PostgreSQL < 12:

1. **Prefer subqueries** over CTEs for performance-critical queries
2. **Use CTEs only** for readability (non-hot paths)
3. **Use LATERAL** for correlated subqueries
4. **Consider materialized views** for repeated aggregations

### For PostgreSQL 12+:

1. **CTEs are fine** - they're optimized like subqueries
2. **Use `MATERIALIZED`** only when intentional
3. **Still prefer subqueries** for simple cases (clearer intent)

---

## Real Incident Reference

Many companies hit this issue when using ORMs that generate CTEs. The "CTE performance problem" was a major pain point until PostgreSQL 12's optimization improvements.

**Common pattern:** ORM generates CTEs → Slow queries → Rewrite as subqueries → Problem solved.

---

## Trade-offs

| Approach | Readability | Performance | Maintenance |
|----------|-------------|-------------|--------------|
| CTE (multi-step) | High (good) | Low (< 12), High (12+) | Good |
| Subquery (nested) | Low (hard) | High | Poor (nested) |
| LATERAL | Medium | High | Good |
| Materialized view | High | Very High | Medium (refresh) |
| Separate queries | High | High | Good |

**Recommendation:** For PostgreSQL < 12, prefer subqueries/LATERAL for hot paths. For PostgreSQL 12+, use CTEs for readability.

---

**Next Problem:** `advanced/incident-100-distributed-deadlock/`
