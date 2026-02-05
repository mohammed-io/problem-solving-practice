# Step 01: Why Isn't the Index Being Used?

---

## The Index Mystery

You created an index on `email`, but PostgreSQL is ignoring it.

**EXPLAIN ANALYZE shows:**
```
Seq Scan on users  (cost=0.00..5234.56 rows=1 width=64)
  Filter: (email = 'user@example.com'::text)
```

A **Seq Scan** means PostgreSQL is reading the entire table row by row.

---

## Question 1: How Many Rows Are in the Table?

**Check:**
```sql
SELECT COUNT(*) FROM users;
```

**What this tells you:**
- If **< 1000 rows**: Sequential scan is correct! Reading all rows is faster than index lookup.
- If **> 10,000 rows**: Sequential scan is wrong! Index should be used.

**Why?**
- Index lookup = 2 I/Os (index read + table read)
- Sequential scan = N I/Os (where N = table pages)
- For small tables, N is small, so Seq Scan wins

---

## Question 2: Is the Data Type Matching?

**Check:**
```sql
-- What type is the column?
\d users

-- Or:
SELECT attname, typname
FROM pg_attribute a
JOIN pg_type t ON a.atttypid = t.oid
WHERE attrelid = 'users'::regclass AND attname = 'email';
```

**What to look for:**
- Column type: `VARCHAR(255)` or `TEXT`?
- Query type: Are you comparing with `VARCHAR` or `TEXT`?

**Mismatch example:**
```sql
-- Bad: implicit cast
SELECT * FROM users WHERE email = 123;  -- integer compared to text

-- Bad: function on column
SELECT * FROM users WHERE LOWER(email) = 'user@example.com';
```

**When implicit cast happens, PostgreSQL can't use the index.**

---

## Question 3: What If Table Is Huge But Still No Index?

If table has millions of rows but still not using index, check:

**1. Is the index actually created?**
```sql
\d users  -- Look for "Indexes:" section

-- Or:
SELECT indexname FROM pg_indexes WHERE tablename = 'users';
```

**2. Are statistics outdated?**
```sql
ANALYZE users;  -- Update statistics
```

**3. Is there a function on the column?**
```sql
-- This can't use index on email:
SELECT * FROM users WHERE LOWER(email) = 'user@example.com';

-- Solution: Create functional index
CREATE INDEX idx_users_email_lower ON users(LOWER(email));
```

---

**Still stuck? Read `step-02.md`**

---

## Quick Check

Before moving on, make sure you understand:

1. Why would PostgreSQL ignore an index? (Small table, type mismatch, function on column)
2. What's a Seq Scan? (Sequential scan - reading entire table row by row)
3. Why is index lookup 2 I/Os? (Index read + table read for row data)
4. When is Seq Scan faster than index? (Small tables < ~1000 rows)
5. What prevents index use with LOWER(email)? (Function on column prevents index use)

