---
name: postgres-103-schema-migration
description: Zero-Downtime Schema Migration
difficulty: Advanced
category: PostgreSQL / Schema Management
level: Principal Engineer/DBA
---
# PostgreSQL 103: Zero-Downtime Schema Migration

---

## The Situation

You need to add a `status` column to the `orders` table with a default value:

```sql
-- Current table has 10 million rows
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Need to add:
ALTER TABLE orders ADD COLUMN status VARCHAR(20) DEFAULT 'pending';
```

**Concern:** This is a high-traffic production table. Can't afford downtime.

---

## The Incident Report

```
Time: During deployment

Issue: ALTER TABLE locks table, all queries timeout
Impact: Complete outage, 2 minutes downtime
Severity: P0

What happened:
ALTER TABLE orders ADD COLUMN status VARCHAR(20) DEFAULT 'pending';
↓
PostgreSQL: "AccessExclusiveLock" acquired on orders
↓
All queries to orders blocked!
↓
2 minutes later (10M rows updated): Lock released
```

---

## What is AccessExclusiveLock?

PostgreSQL lock modes for ALTER TABLE:

| Lock Mode | Blocks | Description |
|-----------|--------|-------------|
| ACCESS SHARE | No | SELECT queries |
| ROW EXCLUSIVE | No | INSERT, UPDATE, DELETE |
| SHARE | Yes | CREATE INDEX CONCURRENTLY |
| EXCLUSIVE | Yes | REFRESH CONCURRENTLY |
| ACCESS EXCLUSIVE | **Yes (everything)** | ALTER TABLE, DROP, TRUNCATE |

**ALTER TABLE with DEFAULT** requires ACCESS EXCLUSIVE LOCK:
- Blocks ALL reads and writes
- Updates all rows (sets default value)
- Can take hours on large tables!

---

## Why ALTER TABLE is Slow

```
ALTER TABLE orders ADD COLUMN status DEFAULT 'pending';

PostgreSQL must:
1. Lock table (ACCESS EXCLUSIVE)
2. Rewrite all 10M rows (add column with default)
3. Update all indexes (include new column)
4. Release lock

Time for 10M rows: ~2-5 minutes depending on hardware
During this time: No reads, no writes!
```

---

## The Challenge

**Requirement:** Add column without downtime.

**Constraints:**
- Table: 10 million rows, 50 GB
- Traffic: 5000 queries/second
- Zero tolerance for downtime
- Must be backward compatible

---

## Jargon

| Term | Definition |
|------|------------|
| **AccessExclusiveLock** | Lock blocking all reads/writes; used by ALTER TABLE |
| **Zero-downtime migration** | Schema change without service interruption |
| **Backward compatible** | Old code works with new schema |
| **Forward compatible** | New code works with old schema |
| **Online DDL** | Schema change without table lock |
| **pg_dump | Split operation into phases |

---

## Questions

1. **How do you add a column without locking the table?**

2. **What's the difference between DEFAULT and NULL?**

3. **How do you handle code that expects the new column?** (Backward compatibility)

4. **What about indexes on the new column?**

5. **As a Principal Engineer, what's the migration checklist?**

---

**When you've thought about it, read `step-01.md`**
