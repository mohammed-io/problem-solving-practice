# Step 01: Understanding N+1

---

## Question 1: How Many Queries Are Being Made?

Let's count:

```javascript
// Query 1: Get products (50 rows)
const products = await db.query(`
    SELECT product_id, name, price, category_id
    FROM products
    ORDER BY created_at DESC
    LIMIT 50
`);  // 1 query

// For each of 50 products:
for (const product of products.rows) {
    const category = await db.query(`
        SELECT name FROM categories WHERE category_id = $1
    `, [product.category_id]);  // 50 queries!
}

// Total: 1 + 50 = 51 queries!
```

This is the **N+1 problem**: 1 initial query + N additional queries.

---

## Why is This Slow?

```
Query 1: SELECT * FROM products LIMIT 50
  → Takes 50ms

Query 2: SELECT name FROM categories WHERE category_id = 1
  → Takes 10ms (network + query overhead)

Query 3: SELECT name FROM categories WHERE category_id = 1
  → Takes 10ms

...

Query 51: SELECT name FROM categories WHERE category_id = 5
  → Takes 10ms

Total: 50ms + (50 × 10ms) = 550ms minimum
With connection pool contention and network latency: 5-10 seconds!
```

---

## Question 2: Fix with JOIN

**Use a single query with JOIN:**

```javascript
const products = await db.query(`
    SELECT
        p.product_id,
        p.name,
        p.price,
        p.category_id,
        c.name as category_name
    FROM products p
    LEFT JOIN categories c ON p.category_id = c.category_id
    ORDER BY p.created_at DESC
    LIMIT 50
`);  // Just 1 query!

// Each row now includes category_name
console.log(products.rows[0].category_name);
```

**Result:** 1 query, ~50ms total, 10-100x faster!

---

## Question 3: Multiple Relationships

**What if you need category, brand, AND vendor?**

```javascript
// OLD: N+1 × 3 = 1 + 150 queries!
for (const product of products) {
    const category = await db.query('SELECT * FROM categories WHERE id = $1', [product.category_id]);
    const brand = await db.query('SELECT * FROM brands WHERE id = $1', [product.brand_id]);
    const vendor = await db.query('SELECT * FROM vendors WHERE id = $1', [product.vendor_id]);
}
```

**FIX: Multiple JOINs**

```javascript
const products = await db.query(`
    SELECT
        p.*,
        c.name as category_name,
        b.name as brand_name,
        v.name as vendor_name
    FROM products p
    LEFT JOIN categories c ON p.category_id = c.category_id
    LEFT JOIN brands b ON p.brand_id = b.brand_id
    LEFT JOIN vendors v ON p.vendor_id = v.vendor_id
    ORDER BY p.created_at DESC
    LIMIT 50
`);  // Still just 1 query!
```

---

## When JOINs Don't Work

**If you have paginated products with many categories, consider:**

```javascript
// 1. Get products
const products = await db.query('SELECT * FROM products LIMIT 50');

// 2. Get all categories in one query
const categoryIds = products.rows.map(p => p.category_id);
const categories = await db.query(`
    SELECT * FROM categories WHERE category_id = ANY($1)
`, [categoryIds]);

// 3. Build lookup map
const categoryMap = new Map(
    categories.rows.map(c => [c.category_id, c])
);

// 4. Attach categories to products
products.rows.forEach(p => {
    p.category = categoryMap.get(p.category_id);
});
```

This is **2 queries instead of 51** - much better!

---

**Now read `solution.md` for complete patterns and examples.**

---

## Quick Check

Before moving on, make sure you understand:

1. What is the N+1 problem? (1 query + N additional queries in loop)
2. Why is N+1 slow? (Network latency per query, connection pool contention)
3. How do JOINs fix N+1? (Single query fetches all related data)
4. What if you have multiple relationships? (Multiple JOINs still 1 query)
5. When don't JOINs work well? (Pagination, complex relationships - use batch queries)

