# Step 2: MVCC and Bloat

---

## Why MVCC Causes Bloat

Every UPDATE creates a new row:

```
Initial:  [row version 1] (xmin=100)
UPDATE:    [row version 1] (xmax=101) [row version 2] (xmin=101)
UPDATE:    [row version 1] (xmax=101) [row version 2] (xmax=102) [row version 3] (xmin=102)
```

Dead rows accumulate until VACUUM removes them.

---

## Long-Running Transactions = Bloat

```
Time 00:00 - Long transaction starts (xmin=1000)
Time 00:05 - 1000 UPDATEs happen (xmin=1001-2000)
Time 01:00 - Long transaction still running
```

PostgreSQL **cannot remove** rows with xmin > 1000 because transaction 1000 might still need to see them!

**Result:** Table has 1000 dead versions that can't be cleaned up.

---

## Checking for Wraparound Danger

```sql
-- Check autovacuum wraparound protection
SELECT relname, age(relfrozenxid), autovacuum_freeze_min_age
FROM pg_class
WHERE relkind = 'r'
ORDER BY age(relfrozenxid) DESC;
```

If `age(relfrozenxid)` approaches 2 billion, transaction ID wraparound is imminent (emergency VACUUM required).

---

## Prevention

```sql
-- Avoid long transactions
-- Use READ COMMITTED (not REPEATABLE READ) unless needed
-- Set aggressive autovacuum for hot tables
ALTER TABLE accounts SET (autovacuum_vacuum_scale_factor = 0.05);

-- Manual freeze for old tables
VACUUM FREEZE accounts;
```

---

## Quick Check

Before moving on, make sure you understand:

1. Why does MVCC cause bloat? (Each UPDATE creates new row version, old versions need cleanup)
2. Why do long-running transactions prevent cleanup? (Vacuum can't remove rows newer than oldest running transaction)
3. What is transaction ID wraparound? (32-bit XIDs wrap around after 2 billion, causes data loss)
4. What is autovacuum? (Automatic process to clean up dead row versions)
5. How do you prevent wraparound? (Regular VACUUM, avoid long transactions, aggressive autovacuum)

---

**Continue to `solution.md`**
