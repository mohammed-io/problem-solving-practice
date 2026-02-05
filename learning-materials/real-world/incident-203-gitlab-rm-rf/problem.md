---
name: incident-203-gitlab-rm-rf
description: System design problem
difficulty: Advanced
category: Real-World / Database / Operations
level: Principal Engineer
---
# Real-World 203: GitLab Database Deletion

---

## The Situation

You're a Site Reliability Engineer at GitLab. You run PostgreSQL in replication setup:

```
Primary DB (db1.cluster.gitlab.com)  - Handles writes
Replica DB (db2.cluster.gitlab.com)  - Read replicas, backups
```

**Replication setup:**

```bash
# On replica (db2)
$ psql -c "SELECT pg_is_in_recovery();"
  pg_is_in_recovery
-------------------
 t
(1 row)

# Replication status
$ psql -c "SELECT * FROM pg_stat_replication;"
 -[ RECORD 1 ]----+---------------------------------
 pid              | 12345
 usesysid         | 16384
 usename          | replication_user
 application_name | walreceiver
 client_addr      | 10.0.1.5
 client_hostname  | db2.cluster.gitlab.com
 state            | streaming
```

---

## The Incident

```
Date: January 2017
Duration: Data loss (24+ hours of writes lost, then fully recovered from snapshot)
Impact: GitLab.com down for several hours

Timeline (from public postmortem):
00:30 UTC - Replication lag detected on db2
01:00 UTC - Engineer begins investigating
01:30 UTC - Confusion about which server is primary
02:00 UTC - Engineer thinks db2 is primary (stale data)
02:15 UTC - Runs `rm -rf /var/lib/postgresql/data` on db2
02:16 UTC - Realizes db2 was actually the REPLICA (not primary)
02:17 UTC - But wait... was it primary or replica?
02:20 UTC - Panic: Checking which server had what data
02:25 UTC - realizes db1 (actual primary) had replication issues too
02:30 UTC - Both databases in inconsistent state
```

---

## The Jargon

| Term | Definition | Analogy |
|------|------------|---------|
| **Streaming Replication** | Primary ships WAL to replica in real-time | Live TV broadcast vs recording |
| **WAL (Write-Ahead Log)** | Journal of all database changes | Transaction ledger |
| **Replication Slot** | Prevents primary from deleting WAL needed by replica | Bookmark: don't delete pages I haven't read |
| **Replica Identity** | How replica identifies rows for updates/deletes | Primary key for replication |
| **pg_is_in_recovery()** | Returns true if server is a replica | "Am I the backup?" |
| **Failover** | Promoting replica to become primary | Backup quarterback starting the game |
| **Switchover** | Planned failover | Scheduled quarterback change |
| **Split Brain** | Both primaries think they're in charge | Two captains giving conflicting orders |
| **Data Directory** `/var/lib/postgresql/data` | Where PostgreSQL stores all data | The vault containing all the money |

---

## What Actually Happened

**The confusion:**

```bash
# Engineer on db2.cluster.gitlab.com
$ hostname
db2.cluster.gitlab.com

$ psql -c "SELECT pg_is_in_recovery();"
  pg_is_in_recovery
-------------------
 t  ← "Wait, this returns TRUE but replication is broken?"

# Engineer checks replication process
$ ps aux | grep walreceiver
  No walreceiver process running

# Engineer concludes: "No walreceiver = must be primary!"
# WRONG: Walreceiver was CRASHED, replica was broken

$ sudo -u postgres psql
postgres=# \x
postgres=# SELECT * FROM pg_stat_replication;
  (0 rows)  ← "No replicas connected, I must be primary!"
  WRONG: This is the REPLICA, it has no replicas of its own

# Engineer thinks they're on primary, needs to fix replication
# Deletes data directory to "reinitialize" replica
$ sudo rm -rf /var/lib/postgresql/data
  ← DELETES PRODUCTION DATA (or thinks it does)
```

**The actual state:**
- `db2` was a replica, but replication was broken
- `db2` had stale data (24+ hours old due to replication failure)
- The `rm -rf` deleted what was already stale data
- BUT confusion about which server was what caused panic

---

## The Deeper Issues

**1. No clear server identification:**
```bash
# No way to tell at a glance
$ cat /etc/postgresql/14/main/postgresql.conf | grep hot_standby
hot_standby = on  ← This means REPLICA, not primary!

# But engineer didn't check this
```

**2. Replication monitoring was broken:**
```bash
# Nagios alert: "Replication lag"
# But didn't specify WHICH server, or WHAT lag
```

**3. No automated failover:**
```bash
# Manual process, runbook confusion
# No automated way to determine "who is primary"
```

**4. Deleting data directory is catastrophic:**
```bash
# This should NEVER be the first step
# Always snapshot before destructive operations
```

---

## Questions

1. **How could you positively identify primary vs replica without ambiguity?**

2. **What monitoring should have been in place to detect replication issues earlier?**

3. **What procedures should prevent `rm -rf` of production data directories?**

4. **How do you safely recover from replication failures?**

5. **As a Principal Engineer, how do you design database operations to prevent this?**

---

**When you've thought about it, read `step-01.md`**
