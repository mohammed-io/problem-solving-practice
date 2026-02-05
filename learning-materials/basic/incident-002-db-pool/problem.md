---
name: incident-002-db-pool
description: Connection pool exhaustion during deployment
difficulty: Basic
category: Incident Response
level: Mid-level
---
# Incident 002: Database Connection Pool Exhaustion

---

## The Situation

You're a Staff Engineer at PaymentsCo. The team just deployed a new version of the payment service.

**Time:** Wednesday, 2:30 PM UTC (15 minutes after deploy)

PagerDuty fires: **"payment-service: error_rate > 1%"**

You jump into the incident channel and see:

```
[14:15] @bot Deployed payment-service v2.3.0 to production
[14:30] @pagerduty 🚨 payment-service: error_rate > 1% for 3m
[14:31] @you Acknowledged
```

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Payment Service                         │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  Node.js app                                          │ │
│  │  - 20 pods (Kubernetes)                               │ │
│  │  - Each pod: 4 workers (cluster)                     │ │
│  │  - Connection pool: 10 connections per worker        │ │
│  └───────────────────────────────────────────────────────┘ │
│                          │                                 │
│                          ▼                                 │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  PostgreSQL (RDS db.m5.2xlarge)                      │ │
│  │  - max_connections: 500                              │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## What You See

### Grafana Dashboard

| Metric | Before Deploy | Now |
|--------|---------------|-----|
| Request Rate | 2000 req/s | 2000 req/s |
| Error Rate | 0.05% | 12.5% |
| p95 Latency | 80ms | 4500ms |
| Active Connections | 380 | 500 (at max!) |
| Connection Wait Time | 1ms | 850ms |

### Application Logs

```
Error: acquire connection timeout
    at ConnectionPool.acquire (/app/node_modules/pg-pool/index.js:245:15)
    at async query (/app/services/payment.js:42:5)
```

### Database Logs (from AWS RDS)

```
2024-11-27 14:31:05 UTC::@:[20345]:LOG: connection authorized: user=payment_app database=production
2024-11-27 14:31:05 UTC::@:[20346]:WARNING: too many connections for role "payment_app"
2024-11-27 14:31:05 UTC::@:[20347]:FATAL: remaining connection slots are reserved for non-replication superuser connections
```

---

## Context from Team

In the incident channel:

```
[14:32] @junior-dev The new feature adds a background job that syncs
payment status to our analytics warehouse. It runs every 30 seconds.

[14:33] @sre-team We didn't change anything in the deploy configs.
Same pod count, same resource limits.
```

---

## Jargon

| Term | Definition |
|------|------------|
| **Connection Pool** | Cache of database connections maintained by the application to avoid overhead of creating new connections for each query |
| **max_connections** | PostgreSQL setting limiting total concurrent connections to the database |
| **Acquire timeout** | How long an application will wait for an available connection from the pool before giving up |
| **Superuser connections** | PostgreSQL reserves some connection slots for admins (so you can still connect even if normal connections are exhausted) |
| **Background job** | Code that runs periodically or asynchronously, not in response to a user request |

---

## Your Task

1. **What changed?** (Think about the new background job)

2. **Calculate the math:**
   - How many connections should the system use?
   - How many is it actually using?
   - Where's the mismatch?

3. **What's the fix?** (Consider both immediate and long-term)

4. **As a Staff Engineer, what systemic issue does this reveal?**

---

**When you've thought about it, read `step-01.md`**
