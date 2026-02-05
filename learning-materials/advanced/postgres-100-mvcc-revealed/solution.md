# Solution: MVCC Revealed

---

## Complete Understanding

### MVCC Visibility Rules

A row is visible to transaction T if ALL of:
1. `row.xmin` is committed (and not in T's snapshot excluded list)
2. `row.xmax` is 0 (not deleted) OR `row.xmax` is NOT committed (or in excluded list)

**In simpler terms:**
- Row created by committed transaction before T started → visible
- Row not deleted, or deleted by uncommitted/future transaction → visible
- Row deleted by committed transaction before T started → NOT visible

### Isolation Levels

| Level | Snapshot Behavior | Non-repeatable Reads | Phantoms |
|-------|------------------|---------------------|----------|
| READ COMMITTED | Per-statement | Possible | Possible |
| REPEATABLE READ | First SELECT | Not possible | Possible |
| SERIALIZABLE | First SELECT | Not possible | Not possible |

### xmin/xmax/ctid Explained

```sql
SELECT id, balance, xmin, xmax, ctid,
       pg_snapshot_xmin(txid_snapshot()) as snapshot_xmin
FROM accounts WHERE id = 1;
```

- **xmin:** Transaction that created this row version
- **xmax:** Transaction that deleted this row (0 = alive)
- **ctid:** Physical location (block, offset) - can change after VACUUM
- **snapshot_xmin:** Oldest transaction still considered active for this snapshot

---

## Diagnosing MVCC Issues

### Check What Transaction Sees

```sql
-- Session 1
BEGIN;
UPDATE accounts SET balance = 900 WHERE id = 1;
-- Don't commit

-- Session 2
BEGIN;
SELECT balance FROM accounts WHERE id = 1;  -- 1000
SELECT txid_snapshot();  -- Shows snapshot info
COMMIT;
```

### Check Dead Tuples

```sql
-- Estimate dead tuples
SELECT
    schemaname,
    relname,
    n_dead_tup,
    n_live_tup,
    round(100 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) as dead_ratio
FROM pg_stat_user_tables
WHERE n_live_tup > 0
ORDER BY dead_ratio DESC;
```

---

## Best Practices

### 1. Avoid Long Transactions

```sql
-- BAD: Transaction open for minutes
BEGIN;
SELECT * FROM large_table;
-- ... application logic ...
UPDATE accounts ...;
COMMIT;

-- GOOD: Minimize transaction time
-- Application logic outside transaction
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;
```

### 2. Choose Right Isolation Level

```sql
-- Use READ COMMITTED for most operations (default)
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;

-- Use REPEATABLE READ only when needed (consistency within transaction)
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;

-- Use SERIALIZABLE rarely (true serializable execution, expensive)
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
```

### 3. Monitoring

```sql
-- Long-running transactions
SELECT
    pid,
    now() - xact_start as duration,
    query
FROM pg_stat_activity
WHERE state IN ('idle in transaction', 'active')
ORDER BY duration DESC;

-- Transaction wraparound risk
SELECT
    relname,
    age(relfrozenxid),
    autovacuum_freeze_max_age - age(relfrozenxid) as remaining
FROM pg_class
WHERE relkind = 'r'
ORDER BY age(relfrozenxid) DESC;
```

---

## Key Takeaways

1. **Snapshots are taken at statement start (READ COMMITTED) or first SELECT (REPEATABLE READ)**
2. **Long-running transactions prevent VACUUM from cleaning up dead tuples**
3. **MVCC means no reader-writer blocking, but more complex visibility rules**
4. **Transaction IDs wrap around at ~2 billion - requires VACUUM FREEZE to prevent**
5. **Use READ COMMITTED by default, upgrade only when needed**

---

## Real Incident Reference

Many production issues stem from:
- Long-running transactions preventing cleanup (bloat)
- Misunderstanding isolation level (seeing stale data)
- Transaction ID wraparound (emergency VACUUM interrupts service)

Understanding MVCC is crucial for PostgreSQL operations at scale.

---

**All Problems Complete!**
