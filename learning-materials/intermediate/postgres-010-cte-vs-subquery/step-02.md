# Step 2: Understanding the Solutions

---

## Solution 1: Use Subqueries Instead

**Before (CTE):**
```sql
WITH monthly_sales AS (
    SELECT DATE_TRUNC('month', order_date) AS month, ...
    FROM orders
    WHERE order_date >= NOW() - INTERVAL '12 months'
    GROUP BY 1
)
SELECT * FROM monthly_sales;
```

**After (Subquery):**
```sql
SELECT * FROM (
    SELECT DATE_TRUNC('month', order_date) AS month, ...
    FROM orders
    WHERE order_date >= NOW() - INTERVAL '12 months'
    GROUP BY 1
) AS monthly_sales;
```

**Why this helps:** Subqueries can be inlined and optimized by PostgreSQL. The optimizer can push predicates, use indexes, and choose better join strategies.

---

## Solution 2: Use LATERAL Joins

For your specific query, use `LATERAL`:

```sql
SELECT
    ms.monthly_trend,
    tp.top_products,
    rp.regional_performance
FROM (SELECT 1) AS dummy
LEFT JOIN LATERAL (
    SELECT JSON_AGG(json_build_object('month', month, 'sales', sales_total, 'orders', order_count)) AS monthly_trend
    FROM (
        SELECT DATE_TRUNC('month', order_date) AS month, SUM(total_amount) AS sales_total, COUNT(*) AS order_count
        FROM orders
        WHERE order_date >= NOW() - INTERVAL '12 months'
        GROUP BY DATE_TRUNC('month', order_date)
    ) AS sub
) AS ms ON true
LEFT JOIN LATERAL (
    SELECT JSON_AGG(json_build_object('product', name, 'sold', total_sold)) AS top_products
    FROM (
        SELECT p.name, SUM(oi.quantity) AS total_sold
        FROM order_items oi
        JOIN products p ON p.product_id = oi.product_id
        JOIN orders o ON o.order_id = oi.order_id
        WHERE o.order_date >= NOW() - INTERVAL '12 months'
        GROUP BY p.product_id, p.name
        ORDER BY total_sold DESC
        LIMIT 10
    ) AS sub
) AS tp ON true;
```

**Why this helps:** `LATERAL` allows subqueries to reference columns from previous queries in FROM, and each subquery is optimized independently.

---

## Solution 3: Upgrade PostgreSQL

**PostgreSQL 12+** automatically inlines CTEs unless you specify `MATERIALIZED`:

```sql
-- Postgres 12+: Auto-inlined (fast)
WITH cte AS (SELECT ...)
SELECT * FROM cte;

-- Postgres 12+: Force materialization if needed
WITH cte AS MATERIALIZED (SELECT ...)
SELECT * FROM cte;
```

---

## Solution 4: Separate Queries

Sometimes the best solution is **multiple queries**:

```sql
-- Query 1: Monthly sales
SELECT JSON_AGG(...) AS monthly_trend
FROM orders ...
-- → Cached in application

-- Query 2: Top products
SELECT JSON_AGG(...) AS top_products
FROM ...
-- → Cached in application

-- Query 3: Regional
SELECT JSON_AGG(...) AS regional_performance
FROM ...
```

**Benefits:**
- Each query independently optimized
- Can cache results at application level
- Easier to understand and maintain

---

**Continue to `solution.md`**

---

## Quick Check

Before moving on, make sure you understand:

1. When should you use subqueries instead of CTEs? (PostgreSQL < 12, need optimization)
2. What's a LATERAL join? (Allows subqueries to reference columns from previous queries in FROM)
3. What changed in PostgreSQL 12? (CTEs are auto-inlined unless MATERIALIZED specified)
4. What's MATERIALIZED keyword? (Forces CTE to be materialized instead of inlined)
5. When are separate queries better? (When you can cache results, need independent optimization)
