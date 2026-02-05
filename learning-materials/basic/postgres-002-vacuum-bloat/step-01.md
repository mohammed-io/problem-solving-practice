# Step 01: Understanding MVCC and Bloat

---

## Question 1: Why Does MVCC Cause Bloat?

**MVCC = Multi-Version Concurrency Control**

When you UPDATE a row in PostgreSQL:
1. **New row is written** with the new data
2. **Old row is marked "dead"** but not removed
3. **Dead rows accumulate** → bloat!

```sql
UPDATE users SET email = 'new@example.com' WHERE id = 1;
```

**What actually happens:**
```
Before:
| id | email                |
|----|----------------------|
| 1  | old@example.com      |

After:
| id | email                | xmin (created) | xmax (deleted) |
|----|----------------------|----------------|----------------|
| 1  | old@example.com      | 1000          | 1001           | ← DEAD
| 1  | new@example.com      | 1001          |               | ← LIVE
```

The old row stays in the table until VACUUM removes it.

**DELETE is similar:**
```sql
DELETE FROM users WHERE id = 1;
```

Row is marked dead but space isn't immediately reclaimed.

---

## Question 2: VACUUM vs VACUUM FULL

| Operation | What It Does | Locks Table? | Reclaims Space? |
|-----------|--------------|--------------|-----------------|
| **VACUUM** | Marks dead tuples as reusable | No (minor) | No (space reused by new rows) |
| **VACUUM FULL** | Rewrites entire table compactly | Yes (exclusive) | Yes (returns space to OS) |

**VACUUM (regular):**
- Dead space can be used for new rows in same table
- Table doesn't shrink on disk
- Can run while database is active

**VACUUM FULL:**
- Creates new compact copy of table
- Deletes old file, returns space to OS
- **Locks table** - no reads/writes during operation

---

## Question 3: Why Doesn't Autovacuum Keep Up?

**Autovacuum is PostgreSQL's background cleanup process.**

**Check if it's running:**
```sql
SELECT * FROM pg_stat_user_tables WHERE relname = 'users';
```

**Look at:**
- `autovacuum_count`: How many times it ran
- `last_autovacuum`: When it last ran
- `autovacuum_count` should be increasing periodically

**Common reasons autovacuum falls behind:**

1. **Too many UPDATES/DELETES**
   ```sql
   -- If you bulk delete millions of rows
   DELETE FROM events WHERE created_at < '2023-01-01';
   -- Autovacuum can't keep up!
   ```

2. **Autovacuum disabled or throttled**
   ```sql
   SHOW autovacuum;  -- Should be 'on'
   SHOW autovacuum_max_workers;  -- Number of workers
   ```

3. **Table too large relative to autovacuum settings**
   ```sql
   -- Autovacuum triggers when 20% of rows are dead (default)
   -- For billion-row tables, that's 200M dead rows!
   ```

---

**Still thinking? Read `step-02.md`**

---

## Quick Check

Before moving on, make sure you understand:

1. Why does MVCC cause bloat? (Updates create new rows, old rows marked dead)
2. What's the difference between VACUUM and VACUUM FULL? (VACUUM marks reusable, FULL reclaims space)
3. Does VACUUM FULL lock the table? (Yes, exclusive lock during rewrite)
4. What's autovacuum? (Background process that marks dead tuples)
5. Why doesn't autovacuum keep up? (Too many updates, disabled, large table threshold)

