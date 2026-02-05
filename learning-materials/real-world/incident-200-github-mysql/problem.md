---
name: incident-200-github-mysql
description: DNS outage caused by MySQL failover
difficulty: Advanced
category: Real Incident / Database / Failover
level: Principal Engineer
---
# Real Incident 200: GitHub's MySQL Failover Disaster

---

## The Situation

GitHub's architecture uses MySQL with failover:

```
┌─────────────────────────────────────────────────────────────┐
│                     Primary Database                          │
│                      (db-0.primary)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Replication
          ┌──────────────┴──────────────┐
          │                             │
          ▼                             ▼
┌─────────────────────┐         ┌─────────────────────┐
│   Replica 1         │         │   Replica 2         │
│  (db-1.replica)      │         │  (db-2.replica)      │
└─────────────────────┘         └─────────────────────┘
```

**Routing:** Proxy (HAProxy) routes writes to primary, reads to replicas.

---

## The Incident Report

```
Date: October 2022
Duration: 7 hours outage
Impact: GitHub.com completely inaccessible
Severity: P0 (complete service outage)

Root Cause: MySQL failover during maintenance caused database IP change
but HAProxy cached the old IP address in DNS TTL.

Timeline:
20:00 UTC - Planned maintenance: Replace primary database
20:05 - Failover initiated, Replica 1 promoted to primary
20:10 - Application servers still connecting to old IP
20:15 - Identified: DNS cache issue
20:30 - Fixed DNS, set short TTL
03:00 UTC - Full service restored after full cache expiration
```

---

## What Happened

**The failover process:**

1. Old primary: `10.0.0.1` (db-0.primary)
2. Replica 1 promoted to new primary
3. New primary gets NEW IP: `10.0.0.10` (old IP can't be reused immediately)
4. HAProxy config updated to point to `10.0.0.10`
5. But: Application servers cache DNS lookup!

**The problem:**
- Application servers have database connection pool
- Pool has connections to `10.0.0.1`
- New primary is at `10.0.0.10`
- App tries to connect to `10.0.0.1` → Refused!
- App doesn't know to re-lookup DNS

**Worse:** DNS TTL was set to 5 minutes
- Old DNS record cached globally for 5 minutes
- Even after GitHub updated DNS, cached records pointed to wrong IP

---

## The Complexity

```
┌─────────────────────────────────────────────────────────────┐
│                    DNS Layer                                │
│  db-0.primary.github.net → 10.0.0.1 (cached for 300s)     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼ DNS lookup (cached)
┌─────────────────────────────────────────────────────────────┐
│                  Application Servers                          │
│  Each has connection pool to 10.0.0.1 (old primary IP)       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼ Try to connect
┌─────────────────────────────────────────────────────────────┐
│                  HAProxy / Proxy                              │
│  Points to new primary 10.0.0.10                            │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼ New primary
┌─────────────────────────────────────────────────────────────┐
│                  New Primary (was Replica 1)                  │
│                      10.0.0.10                             │
└─────────────────────────────────────────────────────────────┘
```

**App servers never re-lookup DNS!** They keep using old cached IP.

---

## Jargon

| Term | Definition |
|------|------------|
| **Failover** | Promoting replica to primary when primary fails |
| **DNS caching** | DNS records cached locally/regionally for TTL duration |
| **DNS TTL** | Time-to-Live; how long DNS records are cached |
| **Connection pool** | Reusable database connections; must be flushed on IP change |
| **HAProxy** | TCP/HTTP proxy with health checks; routes traffic to backends |
| **Promotion** | Replica becoming primary |
| **Split brain** | Two nodes both think they're primary (bad!) |

---

## Questions

1. **Why didn't HAProxy detect the primary was down?** (Health check issue)

2. **How do you safely failover with minimal downtime?** (Connection draining, DNS strategy)

3. **What's the role of connection pooling in failover?** (Pool must be invalidated)

4. **How do you coordinate DNS TTL with failover speed?** (Lower TTL before failover)

5. **As a Principal Engineer, how do you design systems resilient to failover?**

---

**When you've thought about it, read `step-01.md`**
