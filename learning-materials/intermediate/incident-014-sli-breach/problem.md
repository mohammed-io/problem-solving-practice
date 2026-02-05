---
category: Observability / SRE
description: SLO-based error budget management
difficulty: Intermediate
level: Staff Engineer
name: incident-014-sli-breach
---

# Incident 014: SLI Breach

---

## The Situation

Your team runs an API service with defined service level objectives (SLOs):

**SLO:** 99.9% availability monthly (= 43.2 minutes of downtime allowed per month)
**Measurement:** Successful HTTP requests / Total HTTP requests

**Architecture:**
```
┌────────────────────────────────────────────────────────────┐
│                       Load Balancer                        │
│                  (Health checks: /health)                  │
└────────────────────────┬───────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   API 1     │ │   API 2     │ │   API 3     │
│  (Primary)  │ │  (Primary)  │ │  (Primary)  │
│  us-east-1a │ │  us-east-1b │ │  us-east-1c │
└─────────────┘ └─────────────┘ └─────────────┘
```

---

## The Incident Report

```
Time: Thursday, 9:00 AM UTC

Issue: Customers reporting intermittent 503 errors
Impact: API health dashboard showing 95% availability (below 99.9% SLO)
Severity: P1 (SLO breach)

Error Budget Status: BURNED
  - Allowed downtime: 43.2 minutes/month
  - Actual downtime: 129 minutes (3x over budget!)
```

---

## What is an SLI and SLO?

**SLI (Service Level Indicator):** A metric that measures service performance
- Example: "Ratio of successful HTTP requests to total requests"
- Example: "Ratio of requests with latency < 100ms"

**SLO (Service Level Objective):** A target value for an SLI
- Example: "99.9% of requests succeed"
- Example: "95% of requests complete in < 100ms"

**Error Budget:** The amount of "failure" you're allowed
- 99.9% SLO = 0.1% error budget = 43.2 minutes downtime/month
- When error budget is burned, you stop making features and fix reliability!

---

## What You See

### Grafana Dashboard

```
Availability (24 hours)

99.9% │          ╭─────╮
      │         ╱       ╲
99.5% │        ╱         ╲
      │    ╭───╯           ╲
99.0% │   ╱                   ╲
      │  ╱                      ╲─────╮
95.0% │ ╱                              ╲
      │╱                                ╲
      └─┬────┬────┬────┬────┬────┬────┬────┬────
        00   04   08   12   16   20   23   (hour)
                ↑
            Incident starts
```

### Prometheus Queries

**Current availability:**
```promql
# Successful requests / Total requests
sum(rate(http_requests_total{status!~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))

Result: 0.949 (94.9% - BELOW SLO!)
```

**Requests by status code:**
```promql
sum by (status) (rate(http_requests_total[5m]))

Result:
status="200" → 950 rps
status="500" → 30 rps
status="503" → 20 rps
```

**Instance health:**
```promql
up{job="api"}

Result:
instance="api-1": 0 (DOWN)
instance="api-2": 1 (UP)
instance="api-3": 1 (UP)
```

### Load Balancer Logs

```
09:00:00 [INFO] Health check passed for api-1
09:05:23 [ERROR] Health check failed for api-1: timeout
09:05:23 [WARN] Removing api-1 from rotation
09:05:30 [INFO] All traffic to api-2, api-3
09:15:00 [INFO] Health check passed for api-2
09:15:00 [INFO] Health check passed for api-3
09:25:00 [ERROR] api-3: CPU 95%, memory 87%
09:25:00 [WARN] api-3: Request latency > 5s (SLA: 100ms)
```

---

## Analysis

Looking at the data:

1. **api-1 went down at 09:05:23** - removed from rotation
2. **api-2 and api-3 took all traffic** - normally OK
3. **But api-3 started struggling** - high CPU, high latency
4. **503 errors increased** - load balancer rejecting requests

### What's the SLO Calculation?

```
Monthly budget: 43.2 minutes = 2592 seconds

Current status (day 15 of month):
- Total seconds in 15 days: 1,296,000 seconds
- Allowed downtime: 1,296,000 × 0.001 = 1,296 seconds (~21.6 minutes)
- Used so far: 7,740 seconds (129 minutes)

Error budget remaining: NEGATIVE 6,444 seconds!
```

**We're 3x over our error budget!**

---

## Jargon

| Term | Definition |
|------|------------|
| **SLI** | Service Level Indicator - Metric measuring service performance (latency, error rate, availability) |
| **SLO** | Service Level Objective - Target value for SLI (e.g., "99.9% availability") |
| **SLA** | Service Level Agreement - Contract with customers specifying penalties for SLO misses |
| **Error budget** | Amount of "failure" allowed; 99.9% = 0.1% budget; when burned, stop features |
| **Burn rate** | How fast error budget is being consumed; "100x burn rate" = 100x faster than allowed |
| **503 error** | "Service Unavailable" - Server overloaded or down |
| **Health check** | Endpoint (/health) that load balancer pings to check if instance is alive |
| **Request budget** | Max requests per second a service can handle |

---

## Questions

1. **Why did api-3 struggle after api-1 went down?** (Think about capacity)

2. **Is this really an SLO breach?** (Could the SLO be wrong?)

3. **What's the relationship between SLI, SLO, and SLA?**

4. **How do you prevent this from happening again?**

5. **As a Staff Engineer, how do you design SLOs that are meaningful but achievable?**

---

**When you've thought about it, read `step-01.md`**
