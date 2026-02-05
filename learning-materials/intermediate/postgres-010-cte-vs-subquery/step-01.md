# Step 1: Analyze the Query Execution

---

## How Many Times is `orders` Scanned?

Looking at the EXPLAIN output:

```
CTE monthly_sales:
    -> Seq Scan on orders  (1st scan)

CTE top_products:
    -> Hash Join
         -> Seq Scan on orders  (2nd scan)

CTE regional_performance:
    -> Hash Join
         -> Seq Scan on orders  (3rd scan)

Plus: Each InitPlan re-scans the materialized CTEs!
```

**The `orders` table is scanned 3 times!**

Each scan processes ~500,000 rows (12 months of orders).

---

## The Materialization Problem

**CTE behavior in PostgreSQL < 12:**

```
WITH cte AS (
    SELECT ... FROM big_table  -- Materialized: all results stored
)
SELECT * FROM cte WHERE id = 123;  -- Filters AFTER materialization!
```

**Subquery behavior:**

```
SELECT * FROM (
    SELECT ... FROM big_table
) AS sub WHERE id = 123;  -- Filter pushed INTO subquery!
```

The subquery version can use indexes, apply predicates early. The CTE version materializes everything first.

---

## The Real Issue

Your query has:
1. **3 independent CTEs** (good - they're independent)
2. **3 subqueries in SELECT** that scan each CTE (bad - re-scanning)

```
WITH monthly_sales AS (SELECT ...),      -- Scan orders
     top_products AS (SELECT ...),        -- Scan orders again
     regional_performance AS (SELECT ...) -- Scan orders again
SELECT
    (SELECT * FROM monthly_sales),        -- Re-scan monthly_sales
    (SELECT * FROM top_products),         -- Re-scan top_products
    (SELECT * FROM regional_performance)  -- Re-scan regional_performance
```

---

**Continue to `step-02.md`**

---

## Quick Check

Before moving on, make sure you understand:

1. How many times was orders scanned? (3 times - once per CTE)
2. What's CTE materialization in PostgreSQL < 12? (CTE results stored in memory, then scanned)
3. What's the difference between CTE and subquery? (Subqueries can be inlined and optimized)
4. Why are CTEs re-scanned? (Each subquery in SELECT clause re-materializes the CTE)
5. When are CTEs better than subqueries? (When you need multiple references or recursive queries)
