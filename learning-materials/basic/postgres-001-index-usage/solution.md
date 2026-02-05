# Solution: Index Not Used

---

## Common Causes and Fixes

### Cause 1: Small Table

If table has < 10,000 rows, PostgreSQL may choose sequential scan.

**Why:** Reading entire table is faster than index lookup + heap access.

**Fix:** Nothing! PostgreSQL is making the right choice. Index will be used as table grows.

```sql
-- Check row count
SELECT COUNT(*) FROM users;  -- If < 10000, seq scan is fine
```

### Cause 2: Data Type Mismatch

```sql
-- Column is VARCHAR, but query uses integer (bad!)
SELECT * FROM users WHERE email = 12345;  -- Won't use index

-- Correct type
SELECT * FROM users WHERE email = 'user@example.com';  -- Uses index
```

### Cause 3: Outdated Statistics

PostgreSQL's query planner uses statistics to decide. If outdated, it makes wrong choice.

```sql
-- Update statistics
ANALYZE users;

-- Try query again
EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'user@example.com';
```

### Cause 4: Function on Column

```sql
-- Using LOWER() prevents index use
SELECT * FROM users WHERE LOWER(email) = 'user@example.com';

-- Fix: Create functional index
CREATE INDEX idx_users_email_lower ON users(LOWER(email));

-- Or query with exact case
SELECT * FROM users WHERE email = 'user@example.com';
```

### Cause 5: Implicit Cast

```sql
-- PostgreSQL adding implicit cast (bad!)
SELECT * FROM users WHERE email = SOME_COLUMN_OF_DIFFERENT_TYPE;

-- Fix: Cast explicitly or ensure types match
SELECT * FROM users WHERE email = text(some_column);
```

---

## How to Force Index Use

```sql
-- Force index (not recommended normally)
SELECT * FROM users WHERE email = 'user@example.com';
-- Change to:
SELECT * FROM users USE INDEX (idx_users_email) WHERE email = 'user@example.com';
```

**Better:** Fix root cause instead of forcing.

---

## Summary Checklist

1. Check row count: Small tables = seq scan is OK
2. Check data types match
3. Run `ANALYZE` to update statistics
4. Avoid functions on indexed columns
5. Create functional index if needed

---

## Real Diagnosis

```sql
-- Check if index exists
SELECT indexname FROM pg_indexes WHERE tablename = 'users';

-- Check index usage
SELECT * FROM pg_stat_user_indexes WHERE relname = 'users';

-- Full diagnostic
EXPLAIN (ANALYZE, BUFFERS, VERBOSE) SELECT * FROM users WHERE email = 'user@example.com';
```

The `BUFFERS` option shows actual I/O, helping understand why sequential scan might be faster for small tables.
