# Step 02: ORM Solutions and Prevention

---

## ORM/Query Builder Solutions

### Sequelize (Node.js)

```javascript
// BAD: N+1
const products = await Product.findAll();
for (const product of products) {
  const category = await product.getCategory();  // N queries!
}

// GOOD: Eager loading
const products = await Product.findAll({
  include: [{
    model: Category,
    as: 'category'
  }]
});
// Generates: SELECT * FROM products LEFT JOIN categories ...
```

### TypeORM (Node.js/TypeScript)

```typescript
// BAD: N+1
const products = await productRepository.find();
for (const product of products) {
  const category = await product.category;  // N queries!
}

// GOOD: Eager loading with JOIN
const products = await productRepository.find({
  relations: ['category']
});

// GOOD: Join with query builder
const products = await productRepository.createQueryBuilder('product')
  .leftJoinAndSelect('product.category', 'category')
  .getMany();
```

### Prisma

```typescript
// BAD: N+1
const products = await prisma.product.findMany();
for (const product of products) {
  const category = await prisma.category.findUnique({  // N queries!
    where: { id: product.categoryId }
  });
}

// GOOD: Eager loading with include
const products = await prisma.product.findMany({
  include: {
    category: true
  }
});
```

### Django (Python)

```python
# BAD: N+1
products = Product.objects.all()
for product in products:
    category = product.category  # N queries!

# GOOD: select_related (JOIN)
products = Product.objects.select_related('category').all()

# GOOD: prefetch_related (separate query, then join in Python)
# Use for ManyToMany when JOIN would duplicate rows
products = Product.objects.prefetch_related('tags').all()
```

### ActiveRecord (Ruby)

```ruby
# BAD: N+1
products = Product.all
products.each do |product|
  category = product.category  # N queries!
end

# GOOD: Eager loading
products = Product.includes(:category).all

# GOOD: Explicit JOIN
products = Product.joins(:category).select('products.*, categories.name as category_name')
```

---

## Detecting N+1 in Production

### 1. Query Logging

```javascript
// Add query logger (development only!)
const queryLog = [];

db.on('query', (query) => {
  queryLog.push({ query, time: Date.now() });
});

// After request, check log
app.use((req, res, next) => {
  queryLog.length = 0;  // Clear
  next();

  if (queryLog.length > 10) {
    console.warn(`Possible N+1: ${queryLog.length} queries in one request`);
  }
});
```

### 2. APM Tools

| Tool | What It Does |
|------|-------------|
| **Datadog APM** | Shows query count per request, highlights N+1 |
| **New Relic** | Database visualizer, slow query detection |
| **Sentry** | Performance monitoring, query traces |
| **AppSignal** | Automatic N+1 detection |

### 3. Database Logging

```sql
-- PostgreSQL: Log slow queries
ALTER DATABASE mydb SET log_min_duration_statement = 100;

-- Check for repeated queries
SELECT query, calls, total_time
FROM pg_stat_statements
ORDER BY calls DESC;
```

---

## Prevention Checklist

**Code Review Questions:**
1. Are there loops making database queries?
2. Can this be done with JOIN?
3. Can we fetch all related data in one query?
4. Is the ORM using eager loading?

**Before Deploying:**
1. Run page with query logging enabled
2. Check total query count (< 10 is good)
3. Look for repeated query patterns
4. Load test the page

---

## Summary

| Pattern | Queries | Performance |
|---------|---------|-------------|
| N+1 (loop queries) | 1 + N | Terrible (seconds) |
| JOIN | 1 | Excellent (milliseconds) |
| Two queries + map | 2 | Good (low milliseconds) |
| Eager loading (ORM) | 1-2 | Excellent |

---

**Now read `solution.md` for complete reference.**
