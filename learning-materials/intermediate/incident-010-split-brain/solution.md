# Solution: Replica Lag - Long-Running Query on Primary

---

## Root Cause

**Streaming replication in PostgreSQL is single-threaded.** The replay process on replicas applies WAL entries **sequentially**, one at a time.

If something on the primary generates WAL entries faster than the replica can replay them, lag accumulates.

---

## What Changed

The new activity feed query runs 500 times/second:

```sql
SELECT
  a.*, u.username, u.avatar_url,
  p.content
FROM activities a
JOIN users u ON u.id = a.user_id      -- JOINs can be expensive
JOIN posts p ON p.id = a.post_id      -- especially if no proper indexes
WHERE a.created_at > NOW() - INTERVAL '1 hour'
ORDER BY a.created_at DESC             -- Sort + LIMIT can be expensive
LIMIT 100;
```

### The Problem

This query has **no proper indexes** for the JOINs, so:
1. Postgres does a **sequential scan** on activities table
2. For each matching activity, it does a **nested loop join** on users and posts
3. The query takes **several seconds** to run
4. **During those seconds, the query locks the table**

### Why This Affects Replication

PostgreSQL's replication process:
1. Reads WAL entries and applies them
2. **But**: If a query is holding locks, replay may be blocked
3. The long-running queries generate **more WAL** while blocking replay

The feedback loop:
1. Long query runs → generates WAL
2. Replay tries to apply WAL → blocked by long query
3. More queries pile up → more WAL
4. Lag increases → replica falls further behind

---

## The Fix

### Immediate: Kill the Long-Running Queries

```sql
-- Find long-running queries
SELECT pid, now() - query_start as duration, query
FROM pg_stat_activity
WHERE state = 'active'
  AND now() - query_start > interval '1 minute'
ORDER BY duration DESC;

-- Kill them
SELECT pg_cancel_backend(pid) FROM ...;  -- Graceful
SELECT pg_terminate_backend(pid) FROM ...;  -- Force
```

### Proper Fix: Add Indexes

```sql
-- Index for the activity lookup
CREATE INDEX activities_created_idx
  ON activities (created_at DESC)
  INCLUDE (user_id, post_id);

-- Index for user lookup
CREATE INDEX users_id_idx ON users (id) INCLUDE (username, avatar_url);

-- Index for post lookup
CREATE INDEX posts_id_idx ON posts (id) INCLUDE (content);
```

Now the query uses index-only scans, much faster.

---

## Systemic Prevention

### 1. pg_stat_statements on Primary

```sql
-- Track query performance
SELECT
  query,
  calls,
  total_exec_time / calls as avg_time,
  total_exec_time
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;
```

Alert on queries averaging >100ms.

### 2. Replication Lag Monitoring

```bash
# Alert if replica lag > 60 seconds
watch -n 5 'psql -c "SELECT EXTRACT(EPOCH FROM (NOW() - pg_last_xact_replay_timestamp()))"'
```

### 3. Connection Pooling for Analytics

Don't run analytics queries against the primary:

```
┌─────────────┐
│   Primary   │ ← Only for writes (user posts, comments, likes)
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│  Replica 1  │     │  Replica 2   │
│  (Analytics)│     │  (API reads) │
└─────────────┘     └──────────────┘
```

Analytics queries can run on Replica 1, potentially blocking replay but not affecting API traffic.

---

## Real Incident

**Instagram (2012)**: Postgres replica lag caused by long-running analytics queries on primary. The fix: dedicated replicas for analytics, query timeouts, and proper indexing.

---

## Jargon

| Term | Definition |
|------|------------|
| **Streaming replication** | Primary ships WAL entries to replicas in real-time as they're generated |
| **WAL (Write-Ahead Log)** | Sequential log of all modifications; used for replication and crash recovery |
| **Replay location** | Point in WAL that replica has applied; shows how far behind replica is |
| **Sequential scan** | Reading entire table row-by-row (slow for large tables) |
| **Nested loop join** | For each row in outer table, scan inner table (slow without indexes) |
| **Index-only scan** | Query satisfied entirely from index, no table access needed |
| **pg_stat_statements** | Postgres view showing query execution statistics (calls, total time, etc.) |
| **INCLUDE clause** | Index feature to include extra columns without them being part of search key |

---

## Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| **Kill long queries** | Immediate relief, no code deploy | Breaks user-facing features |
| **Add indexes** | Proper fix, improves performance | Slows down writes, more storage |
| **Separate analytics replica** | Isolation, analytics can be slow | More infrastructure, eventual consistency for analytics |
| **Materialized view** | Pre-computed joins, fast queries | Not real-time, needs refresh |
| **Query timeout** | Prevents runaway queries | May hide real problems |

For this case: **Add indexes** + **Separate analytics replica** is best combination.

---

**Next Problem:** `intermediate/incident-012-hot-partition/`
