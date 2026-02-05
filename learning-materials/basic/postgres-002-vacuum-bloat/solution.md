# Solution: Table Bloat

---

## Why Bloat Happens

PostgreSQL MVCC keeps old versions for concurrency:

```
Transaction 1:  SELECT * FROM users WHERE id = 1;  -- Takes snapshot
Transaction 2:  UPDATE users SET email = 'new' WHERE id = 1;
```

PostgreSQL keeps the old row until Transaction 1 completes. Then it becomes "dead" but space isn't automatically reclaimed.

---

## Immediate Fix: VACUUM FULL

**Warning:** Locks table! Do during maintenance window.

```sql
-- Rewrites table, actually reclaims space
VACUUM FULL users;

-- Or VACUUM FULL with analyze
VACUUM FULL ANALYZE users;
```

After: Table should be ~100 MB instead of 1.8 GB.

---

## Ongoing Prevention: Autovacuum Tuning

Check autovacuum settings:

```sql
SHOW autovacuum;           -- Should be ON
SHOW autovacuum_vacuum_scale_factor;  -- Default: 0.2 (20% of table)
```

**Tune for more aggressive vacuuming:**

```sql
-- Vacuum after 10% of rows are dead (not 20%)
ALTER TABLE users SET (autovacuum_vacuum_scale_factor = 0.1);

-- Or vacuum after 1000 dead rows (not just by percentage)
ALTER TABLE users SET (autovacuum_vacuum_threshold = 1000);
```

---

## Manual VACUUM (Non-locking)

Regular VACUUM (not FULL) doesn't lock but only marks space reusable:

```sql
-- Safe to run anytime, doesn't reclaim disk space
VACUUM users;

-- VACUUM with analyze (updates statistics too)
VACUUM ANALYZE users;
```

---

## When to Use Which

| Command | Locks Table | Reclaims Space | When to Use |
|---------|-------------|----------------|-------------|
| `VACUUM` | No | No (marks reusable) | Regular maintenance |
| `VACUUM FULL` | Yes | Yes | Severe bloat, maintenance window |
| `VACUUM ANALYZE` | No | No | Update statistics |

---

## Monitoring Bloat

```sql
-- Check if vacuum is keeping up
SELECT
    relname,
    n_dead_tup,
    n_live_tup,
    round(100 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) as dead_ratio
FROM pg_stat_user_tables
WHERE n_live_tup > 0
ORDER BY dead_ratio DESC;
```

If `dead_ratio` > 10%, autovacuum may not be keeping up.

---

## Best Practices

1. **Monitor dead tuple ratio** regularly
2. **Tune autovacuum** per-table for hot tables
3. **Schedule regular VACUUM ANALYZE** during low-traffic times
4. **Use VACUUM FULL sparingly** (locks table, disrupts service)
5. **Consider `REINDEX`** if indexes are bloated too

---

## Example: Complete Fix

```sql
-- Step 1: Immediate reclamation (during maintenance)
VACUUM FULL ANALYZE users;

-- Step 2: Tune for prevention
ALTER TABLE users SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_vacuum_threshold = 500
);

-- Step 3: Monitor
SELECT * FROM pg_stat_user_tables WHERE relname = 'users';
```

---

## Key Insight

Bloat is normal in PostgreSQL! MVCC design trades some space for concurrency. Autovacuum normally manages this, but high-activity tables may need tuning.
