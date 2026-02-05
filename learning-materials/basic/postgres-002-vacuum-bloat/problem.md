---
name: postgres-002-vacuum-bloat
description: Table Bloat
difficulty: Basic
category: PostgreSQL / Maintenance
level: Junior to Mid-level
---
# PostgreSQL 002: Table Bloat

---

## The Situation

Your PostgreSQL database is growing unexpectedly fast.

**Table stats:**
```sql
SELECT
    pg_size_pretty(pg_total_relation_size('users')) as total_size,
    pg_size_pretty(pg_relation_size('users')) as table_size,
    pg_size_pretty(pg_total_relation_size('users') - pg_relation_size('users')) as index_size;
```

**Result:**
```
total_size | table_size | index_size
-----------+------------+------------
2.1 GB     | 1.8 GB     | 300 MB
```

But counting rows:
```sql
SELECT COUNT(*) FROM users;  -- Returns: 500,000 rows
```

**Expected size for 500k rows:** ~100 MB
**Actual size:** 1.8 GB

**The table is 18x larger than it should be!**

---

## What is Table Bloat?

Imagine a notebook where you write notes. When you make a mistake, you cross it out and write on the next page.

**Over time:** Many crossed-out pages, but few actual notes.

**In PostgreSQL:** When you `UPDATE` or `DELETE`, old rows are marked dead but space isn't reclaimed. This is "bloat."

---

## How MVCC Causes Bloat

PostgreSQL uses MVCC (Multi-Version Concurrency Control):

```
UPDATE users SET email = 'new@example.com' WHERE id = 1;
```

**What happens:**
1. New row written with new email
2. Old row marked "dead" but not removed
3. Dead rows accumulate → bloat!

**DELETE is similar:**
```
DELETE FROM users WHERE id = 1;
```
Row marked dead but space not reclaimed.

---

## What You See

### Check Bloat

```sql
-- Approximate bloat percentage
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    pg_stat_get_dead_tuples(c.oid) as dead_tuples
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE relname = 'users';
```

**Result shows many dead tuples!**

### Autovacuum Status

```sql
SELECT * FROM pg_stat_user_tables WHERE relname = 'users';
```

Look at:
- `autovacuum_count`: Has autovacuum run?
- `dead_row_count`: How many dead rows?
- `last_autovacuum`: When did it last run?

---

## Jargon

| Term | Definition |
|------|------------|
| **Bloat** | Empty space in data files from deleted/updated rows |
| **MVCC** | Multi-Version Concurrency Control; PostgreSQL keeps old versions for consistency |
| **Dead tuple** | Row that's been deleted or updated; not visible to any transaction |
| **VACUUM** | PostgreSQL command that marks dead tuples as reusable |
| **VACUUM FULL** | Rewrites entire table; actually reclaims space (locks table) |
| **Autovacuum** | Background process that automatically runs VACUUM |

---

## Questions

1. **Why does MVCC cause bloat?**

2. **What's the difference between VACUUM and VACUUM FULL?**

3. **Why doesn't autovacuum keep up?**

4. **How do you reclaim space from bloated table?**

---

**When you've thought about it, read `solution.md`**
