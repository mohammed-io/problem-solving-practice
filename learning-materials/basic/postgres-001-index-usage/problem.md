---
name: postgres-001-index-usage
description: Index Not Used
difficulty: Basic
category: PostgreSQL / Performance
level: Junior to Mid-level
---
# PostgreSQL 001: Index Not Used

---

## The Situation

You have a users table with an index on email:

```sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    username VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
```

You run a query:

```sql
EXPLAIN ANALYZE
SELECT * FROM users WHERE email = 'user@example.com';
```

**Output:**
```
Seq Scan on users  (cost=0.00..5234.56 rows=1 width=64) (actual time=45.123..123.456 rows=1 loops=1)
  Filter: (email = 'user@example.com'::text)
```

**Problem:** It's doing a sequential scan (reading entire table) instead of using the index!

---

## What is an Index?

Imagine a textbook without an index. To find "PostgreSQL" in the book, you'd scan every page.

**With an index:** You look at the index, find the page number, go directly there.

**In databases:** Index is a data structure (B-tree) that allows fast lookups by key.

---

## Why Isn't the Index Used?

**Possible reasons:**
1. **Small table:** If table has few rows, reading everything is faster than index lookup
2. **Data type mismatch:** Comparing different types prevents index use
3. **Function on column:** `WHERE LOWER(email)` can't use index on `email`
4. **Statistics outdated:** PostgreSQL thinks table is small when it's actually large
5. **Low selectivity:** If most rows match (e.g., `WHERE active = true`), index doesn't help

---

## Check Table Size

```sql
-- Check row count
SELECT COUNT(*) FROM users;

-- Check table size
SELECT pg_size_pretty(pg_total_relation_size('users'));
```

If table has < 1000 rows, sequential scan might be correct!

---

## Check Data Types

```sql
-- What type is the email column?
SELECT attname, typname
FROM pg_attribute a
JOIN pg_type t ON a.atttypid = t.oid
WHERE attrelid = 'users'::regclass
  AND attname = 'email';
```

---

## Jargon

| Term | Definition |
|------|------------|
| **Sequential scan** | Reading entire table row by row |
| **Index scan** | Using index to find specific rows |
| **B-tree** | Data structure for indexes; keeps data sorted for fast lookup |
| **Selectivity** | Fraction of rows matching query; lower = better for index |
| **Query plan** | How PostgreSQL executes query; shown by EXPLAIN |
| **EXPLAIN ANALYZE** | Command showing query plan and actual execution time |

---

## Questions

1. **How many rows are in the table?**

2. **Is the email data type matching the query?**

3. **What if the table is huge but still not using index?**

---

**When you've thought about it, read `solution.md`**
