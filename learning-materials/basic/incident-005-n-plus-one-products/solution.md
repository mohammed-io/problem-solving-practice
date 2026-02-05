# Solution: N+1 in Product Catalog

---

## The Fix: Use JOIN

**Before (N+1):**
```javascript
const products = await db.query(`
    SELECT product_id, name, price, category_id
    FROM products
    LIMIT 50
`);

for (const product of products.rows) {
    const category = await db.query(
        'SELECT name FROM categories WHERE category_id = $1',
        [product.category_id]
    );
    product.categoryName = category.rows[0].name;
}
// Total: 51 queries!
```

**After (1 query):**
```javascript
const products = await db.query(`
    SELECT
        p.product_id, p.name, p.price,
        c.name AS category_name
    FROM products p
    LEFT JOIN categories c ON c.category_id = p.category_id
    ORDER BY p.created_at DESC
    LIMIT 50
`);
// Total: 1 query!
```

---

## Performance Comparison

| Approach | Queries | Time |
|----------|---------|------|
| N+1 (loop) | 51 | 5000ms |
| JOIN | 1 | 50ms |

**100x faster!**

---

## Multiple Relationships

For category, brand, and vendor:

```sql
SELECT
    p.product_id, p.name, p.price,
    c.name AS category_name,
    b.name AS brand_name,
    v.name AS vendor_name
FROM products p
LEFT JOIN categories c ON c.category_id = p.category_id
LEFT JOIN brands b ON b.brand_id = p.brand_id
LEFT JOIN vendors v ON v.vendor_id = p.vendor_id
ORDER BY p.created_at DESC
LIMIT 50;
```

Still just 1 query!

---

## ORM Solutions

If using an ORM (like Sequelize, TypeORM, Hibernate):

```javascript
// BAD: N+1
const products = await Product.findAll();
for (const product of products) {
    await product.getCategory();  // Separate query!
}

// GOOD: Eager loading
const products = await Product.findAll({
    include: [{ model: Category }]  // JOIN!
});
```

---

## Key Takeaway

**Always check if you're querying inside a loop.** If yes, use a JOIN (or eager loading in ORM) to fetch all related data in a single query.
