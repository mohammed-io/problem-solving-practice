---
name: incident-005-n-plus-one-products
description: N 1 in Product...
difficulty: Basic
category: Database / Performance
level: Junior to Mid-level
---
# Incident 005: N+1 in Product Catalog

---

## The Situation

Your team runs an e-commerce site. The product catalog page shows 50 products per page.

**Current query:**
```javascript
// Get products
const products = await db.query(`
    SELECT product_id, name, price, category_id
    FROM products
    ORDER BY created_at DESC
    LIMIT 50
`);

// For each product, get category name
for (const product of products.rows) {
    const category = await db.query(`
        SELECT name FROM categories WHERE category_id = $1
    `, [product.category_id]);

    product.categoryName = category.rows[0].name;
}
```

**Problem:** Page takes 5-10 seconds to load.

---

## What is N+1?

**N+1 query problem:** Making N additional queries to get related data.

```
1 query: Get 50 products
+ 50 queries: Get category for each product
= 51 queries total!
```

**Ideally:** Should be 1 query (or 2 at most).

---

## What You See

### Database Logs

```
LOG: execute <unnamed>: SELECT product_id, name, price, category_id FROM products ...
LOG: execute <unnamed>: SELECT name FROM categories WHERE category_id = $1  -- $1 = 1
LOG: execute <unnamed>: SELECT name FROM categories WHERE category_id = $1  -- $1 = 1
LOG: execute <unnamed>: SELECT name FROM categories WHERE category_id = $1  -- $1 = 2
LOG: execute <unnamed>: SELECT name FROM categories WHERE category_id = $1  -- $1 = 1
... (46 more queries)
```

### Timing

- First query: 50ms
- Each category query: 10ms
- Total: 50ms + (50 × 10ms) = 550ms minimum
- With network latency: 5-10 seconds!

---

## Jargon

| Term | Definition |
|------|------------|
| **N+1 query** | Making N additional queries inside a loop instead of fetching all data at once |
| **JOIN** | SQL operation to combine rows from multiple tables |
| **Eager loading** | Loading related data upfront, avoiding N+1 |
| **Lazy loading** | Loading related data only when accessed (can cause N+1) |

---

## Questions

1. **How many queries are being made?**

2. **How do you fix this with JOIN?**

3. **What if you have multiple relationships (category, brand, vendor)?**

---

**When you've thought about it, read `solution.md`**
