---
name: postgres-010-cte-vs-subquery
description: Overuse of ctes in postgresql < 12
difficulty: Intermediate
category: PostgreSQL / Query Optimization
level: Staff Engineer
---
# PostgreSQL 010: CTE vs Subquery

---

## The Situation

Your team has a dashboard showing sales performance. The query uses multiple CTEs (Common Table Expressions, aka `WITH` clauses):

```sql
WITH monthly_sales AS (
    SELECT
        DATE_TRUNC('month', order_date) AS month,
        SUM(total_amount) AS sales_total,
        COUNT(*) AS order_count
    FROM orders
    WHERE order_date >= NOW() - INTERVAL '12 months'
    GROUP BY DATE_TRUNC('month', order_date)
),
top_products AS (
    SELECT
        p.product_id,
        p.name,
        SUM(oi.quantity) AS total_sold
    FROM order_items oi
    JOIN products p ON p.product_id = oi.product_id
    JOIN orders o ON o.order_id = oi.order_id
    WHERE o.order_date >= NOW() - INTERVAL '12 months'
    GROUP BY p.product_id, p.name
    ORDER BY total_sold DESC
    LIMIT 10
),
regional_performance AS (
    SELECT
        r.region_name,
        SUM(o.total_amount) AS regional_sales
    FROM orders o
    JOIN users u ON u.user_id = o.user_id
    JOIN regions r ON r.region_id = u.region_id
    WHERE o.order_date >= NOW() - INTERVAL '12 months'
    GROUP BY r.region_name
)
SELECT
    (SELECT JSON_AGG(json_build_object('month', month, 'sales', sales_total, 'orders', order_count))
     FROM monthly_sales) AS monthly_trend,
    (SELECT JSON_AGG(json_build_object('product', name, 'sold', total_sold))
     FROM top_products) AS top_products,
    (SELECT JSON_AGG(json_build_object('region', region_name, 'sales', regional_sales))
     FROM regional_performance) AS regional_performance;
```

**Problem:** Query takes 8-12 seconds to run.

---

## What is a CTE?

**CTE (Common Table Expression):** Named temporary result set defined using `WITH` clause.

```sql
WITH cte_name AS (
    SELECT ... FROM ...
)
SELECT * FROM cte_name;
```

**Subquery:** Query nested within another query.

```sql
SELECT * FROM (
    SELECT ... FROM ...
) AS subquery_alias;
```

---

## What You See

### EXPLAIN ANALYZE Output

```
CTE Scan on monthly_sales  (cost=0.00..52345.67 rows=1000 width=24) (actual time=5234.123..8456.789 rows=12 loops=1)
  CTE monthly_sales
    -> GroupAggregate  (cost=34567.89..41234.56 rows=1000 width=24)
         -> Sort  (cost=23456.78..31234.56 rows=500000 width=16)
              -> Seq Scan on orders  (cost=0.00..12345.67 rows=500000 width=16)
                   Filter: (order_date >= (now() - '1 year'::interval))

CTE Scan on top_products  (cost=0.00..67890.12 rows=10 width=32) (actual time=3456.789..5678.901 rows=10 loops=1)
  CTE top_products
    -> Limit  (cost=45678.90..67890.12 rows=10 width=32)
         -> Sort  (cost=45678.90..67890.12 rows=100000 width=32)
              -> Hash Join  (cost=12345.67..45678.90 rows=100000 width=32)
                   -> Seq Scan on order_items  (cost=0.00..23456.78 rows=1000000 width=16)
                   -> Hash  (cost=11234.56..11234.56 rows=500000 width=16)
                        -> Seq Scan on orders  (cost=0.00..8901.23 rows=500000 width=16)

CTE Scan on regional_performance  (cost=0.00..45678.90 rows=100 width=32) (actual time=2345.678..3456.789 rows=5 loops=1)
  CTE regional_performance
    -> Hash Aggregate  (cost=34567.89..45678.90 rows=100 width=32)
         -> Hash Join  (cost=12345.67..34567.89 rows=500000 width=32)
              -> Seq Scan on users  (cost=0.00..8901.23 rows=100000 width=16)
              -> Hash  (cost=7890.12..7890.12 rows=500000 width=16)
                   -> Seq Scan on orders  (cost=0.00..5678.90 rows=500000 width=16)

Subquery Scan  ... (actual time=8456.789..8457.012 rows=1 loops=1)
   InitPlan 1 (returns $0)
     -> CTE Scan on monthly_sales  ...
   InitPlan 2 (returns $1)
     -> CTE Scan on top_products  ...
   InitPlan 3 (returns $2)
     -> CTE Scan on regional_performance  ...
```

**Key observation:** The CTEs are materialized (fully computed), then each subquery scans them again.

---

## The PostgreSQL Version Issue

**PostgreSQL < 12:** CTEs are **always materialized** (optimization fence)
```
WITH cte AS (SELECT ... FROM big_table)
SELECT * FROM cte;  -- Full table scan, materialized
```

**PostgreSQL 12+:** CTEs can be inlined (like subqueries)
```
WITH cte AS (SELECT ... FROM big_table)
SELECT * FROM cte;  -- May be inlined, optimized
```

---

## Jargon

| Term | Definition |
|------|------------|
| **CTE (Common Table Expression)** | Named temporary result set using WITH clause; aka "WITH query" |
| **Subquery** | Query nested within another query; can be correlated or uncorrelated |
| **Materialization** | Computing and storing CTE result; optimization fence prevents pushdown |
| **Inlining** | Incorporating CTE/subquery into main query; allows optimizer to work |
| **Optimization fence** | Barrier preventing query optimizer from optimizing across boundaries |
| **Correlated subquery** | Subquery referencing values from outer query; executed per row |
| **Uncorrelated subquery** | Independent subquery; executed once |
| **InitPlan** | Subquery executed once at start (uncorrelated) |
| **SubPlan** | Subquery executed per row (correlated) |

---

## Questions

1. **Why is this query slow?** (Think about materialization)

2. **How many times does the `orders` table get scanned?**

3. **What's the difference between CTE and subquery in PostgreSQL < 12?**

4. **When would you use a CTE vs subquery?**

5. **How do you optimize this query?**

---

**When you've thought about it, read `step-01.md`**
