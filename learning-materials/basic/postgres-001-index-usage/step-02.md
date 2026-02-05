# Step 02: Solving the Index Problem

---

## Common Causes and Solutions

### Cause 1: Small Table

**Diagnosis:**
```sql
SELECT COUNT(*) FROM users;  -- Returns: 500 rows
```

**Solution: Nothing!**

If table has < ~1000 rows, sequential scan is **faster** than index lookup. PostgreSQL is optimizing correctly.

**To force index use (for testing):**
```sql
SET enable_seqscan = OFF;
EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'user@example.com';
-- Don't do this in production!
```

---

### Cause 2: Type Mismatch

**Diagnosis:**
```sql
-- Column is VARCHAR(255)
-- Query uses integer comparison
SELECT * FROM users WHERE email = 123;
```

**Solution: Fix the query**
```sql
-- Correct
SELECT * FROM users WHERE email = 'user@example.com';
```

---

### Cause 3: Function on Column

**Diagnosis:**
```sql
-- Using LOWER() prevents index use
SELECT * FROM users WHERE LOWER(email) = 'USER@EXAMPLE.COM';
```

**Solution 1: Case-insensitive index**
```sql
CREATE INDEX idx_users_email_lower ON users(LOWER(email));

-- Now query uses index
SELECT * FROM users WHERE LOWER(email) = 'USER@EXAMPLE.COM';
```

**Solution 2: Use CITEXT extension (case-insensitive text)**
```sql
CREATE EXTENSION citext;

-- Change column type
ALTER TABLE users ALTER COLUMN email TYPE CITEXT;

-- Now queries are case-insensitive by default
SELECT * FROM users WHERE email = 'USER@EXAMPLE.COM';  -- Uses index!
```

---

### Cause 4: Outdated Statistics

**Diagnosis:**
```sql
-- Table was small when analyzed, now huge
SELECT reltuples::bigint FROM pg_class WHERE relname = 'users';
-- Returns old estimate
```

**Solution:**
```sql
ANALYZE users;  -- Update statistics

-- Check EXPLAIN again
EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'user@example.com';
```

---

### Cause 5: Low Selectivity

**Diagnosis:**
```sql
-- If 90% of rows match, index doesn't help
SELECT * FROM users WHERE active = true;  -- 900,000 out of 1M rows
```

**Solution:** Partial index (index only rows you care about)
```sql
CREATE INDEX idx_users_active_true ON users(id) WHERE active = true;

-- Now query uses index
SELECT * FROM users WHERE active = true;
```

---

## Quick Reference: When Indexes Are Used

| Scenario | Index Used? | Why |
|----------|-------------|-----|
| `WHERE email = 'x'` | ✓ Yes | Exact match on indexed column |
| `WHERE LOWER(email) = 'x'` | ✗ No | Function on column (unless functional index) |
| `WHERE email LIKE 'x%'` | ✓ Yes | Prefix match (B-tree supports) |
| `WHERE email LIKE '%x%'` | ✗ No | Contains check (B-tree doesn't support) |
| `WHERE email = 123` | ✗ No | Type mismatch (implicit cast) |
| `WHERE active = true` | ✓ Maybe | If low selectivity (few rows match) |
| Small table (<1000 rows) | ✗ No | Seq scan is faster |

---

## Key Takeaway

**PostgreSQL is smart.** If it's not using an index, there's usually a reason. Check:
1. Table size (small tables don't need indexes)
2. Type matching (implicit casts prevent index use)
3. Functions on columns (use functional indexes)
4. Statistics accuracy (run ANALYZE)
5. Selectivity (indexes help only when they filter most rows)

---

**Now read `solution.md` for the complete answer.**

---

## Quick Check

Before moving on, make sure you understand:

1. When is Seq Scan correct? (Small tables < 1000 rows, faster than index)
2. What's a functional index? (Index on expression like LOWER(email))
3. What's CITEXT? (Case-insensitive text type, enables case-insensitive index)
4. Why run ANALYZE? (Updates statistics so planner makes correct decisions)
5. What's a partial index? (Index only specific rows using WHERE clause)

