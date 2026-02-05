# Step 02: Fixing Table Bloat

---

## Question 4: How to Reclaim Space?

### Immediate Fix: VACUUM FULL

```sql
-- WARNING: Locks table! Do during maintenance window.
VACUUM FULL users;

-- Check size after
SELECT pg_size_pretty(pg_total_relation_size('users'));
```

**Result:** Table should be ~100MB (down from 1.8GB)

---

### Better Option: pg_repack (No locks!)

If you can't afford downtime:

```bash
# Install pg_repack extension
pg_repack -t users -d mydb

-- Reorganizes table without exclusive lock
-- Can run while application is active
```

---

### Prevent Future Bloat

**1. Tune autovacuum for large tables**

```sql
-- Lower threshold for large tables (trigger vacuum sooner)
ALTER TABLE users SET (autovacuum_vacuum_scale_factor = 0.05);
-- Default is 0.2 (20%); now 5% triggers vacuum

-- Increase cost limit (allow vacuum to work faster)
ALTER TABLE users SET (autovacuum_vacuum_cost_delay = 5);
-- Default is 20ms; lower = more aggressive vacuum
```

**2. Run manual VACUUM after bulk operations**

```sql
-- After large DELETE/UPDATE
DELETE FROM events WHERE created_at < '2023-01-01';
VACUUM events;  -- Not FULL, regular vacuum

-- This marks space as reusable immediately
```

**3. Partition large tables**

```sql
-- Partition by date, drop old partitions instead of DELETE
CREATE TABLE events (
    id BIGSERIAL,
    created_at TIMESTAMPTZ NOT NULL,
    data JSONB
) PARTITION BY RANGE (created_at);

CREATE TABLE events_2023_01 PARTITION OF events
    FOR VALUES FROM ('2023-01-01') TO ('2023-02-01');

-- To delete old data: DROP partition (instant)
DROP TABLE events_2023_01;
```

---

## Monitoring Bloat

**Check current bloat:**
```sql
-- Requires pgstattuple extension
CREATE EXTENSION pgstattuple;

SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    pg_size_pretty(pgstat_tuple_dead_tuple_len(schemaname||'.'||tablename)) as bloat_size,
    round(100 * pgstat_tuple_dead_tuple_len(schemaname||'.'||tablename) /
          pg_total_relation_size(schemaname||'.'||tablename), 2) as bloat_percent
FROM pg_stat_user_tables
WHERE schemaname = 'public';
```

**Set up alerts:**
- Alert if bloat > 30% for any table
- Alert if autovacuum hasn't run in 24 hours
- Alert if dead tuple count > 1M

---

## Summary

| Scenario | Solution | Locks? |
|----------|----------|--------|
| Emergency shrink | `VACUUM FULL users` | Yes |
| Online reorganize | `pg_repack -t users` | No |
| Prevent future bloat | Lower autovacuum thresholds | N/A |
| Bulk deletions | `VACUUM` after DELETE | No |
| Large time-series | Partition by date | N/A |

---

**Now read `solution.md` for complete reference.**

---

## Quick Check

Before moving on, make sure you understand:

1. What's VACUUM FULL? (Rewrites table compactly, locks table, reclaims space)
2. What's pg_repack? (Reorganizes table without exclusive lock)
3. How do you tune autovacuum? (Lower scale_factor, lower cost_delay)
4. Why run VACUUM after bulk DELETE? (Marks space reusable immediately)
5. How does partitioning help bloat? (DROP partition is instant, no vacuum needed)

