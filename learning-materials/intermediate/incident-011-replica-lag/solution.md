# Solution: PostgreSQL Replica Lag

---

## Root Cause

**Streaming replication with insufficient bandwidth + high write volume.**

Primary generates WAL faster than replicas can apply it:
```
Primary: 100 MB/sec WAL generation
Replica link: 50 MB/sec bandwidth
Result: WAL accumulates, lag increases
```

---

## Answers

### 1. Why is Replica Lag Increasing?

**Replica can't keep up with primary's write rate.**

Possible causes:
1. Insufficient network bandwidth between primary and replica
2. Replica hardware slower than primary
3. Replica has additional load (queries, backups, reporting)
4. WAL compression not enabled
5. High write volume on primary

### 2. Monitoring the Lag

```sql
-- On replica: Check replay lag
SELECT
    now() - pg_last_xact_replay_timestamp() AS replication_lag;

-- On replica: Check WAL position difference
SELECT
    pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), sent_lsn)) AS not_sent,
    pg_size_pretty(pg_wal_lsn_diff(sent_lsn, write_lsn)) AS not_written,
    pg_size_pretty(pg_wal_lsn_diff(write_lsn, flush_lsn)) AS not_flushed,
    pg_size_pretty(pg_wal_lsn_diff(flush_lsn, replay_lsn)) AS not_replayed
FROM pg_stat_replication;
```

### 3. Reducing WAL Volume

```sql
-- Reduce WAL size (trade-off: crash recovery longer)
ALTER SYSTEM SET wal_compression = on;      -- Compress WAL
ALTER SYSTEM SET full_page_writes = off;     -- Risky but saves space

-- Reduce checkpoint frequency
ALTER SYSTEM SET checkpoint_timeout = '15 min';
ALTER SYSTEM SET max_wal_size = '8GB';

-- Reload and restart
SELECT pg_reload_conf();
```

### 4. Cascading Replication

```
Primary → Relay Replica → Multiple Replicas

Benefits:
- One stream from primary
- Replicas fan out from relay
- Reduces primary load
```

### 5. Lagging Replica Protection

```sql
-- Application-side timeout
SET statement_timeout = '5s';

-- Or proxy-level (PgBouncer)
-- Query replica, if lag > threshold, route to primary
```

---

## Configuration Template

**postgresql.conf (for replicas):**
```
# Replication settings
max_wal_senders = 10
wal_keep_size = 2GB

# Performance tuning
wal_compression = on
max_worker_processes = 8
max_parallel_workers = 8
```

---

**Now read `step-02.md` for the full recovery procedure.**
