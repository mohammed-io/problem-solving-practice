# Step 09: Building Effective Dashboards

---

## The Problem

The team's dashboards are **monitoring vomit**:

```
❌ Current dashboard:
- 50 graphs on one screen
- CPU, memory, disk, network for every service
- Red/green everywhere
- No context, no priorities

Result: "I don't know where to look!"
```

---

## Solution: Purpose-Built Dashboards

Different roles need different views:

```
┌─────────────────────────────────────────────────────────────┐
│                   ON-CALL DASHBOARD                         │
│  (For: Engineers responding to incidents)                  │
│                                                             │
│  🔴 SLO Status                                              │
│     Availability: 99.85% (target: 99.9%)                   │
│     p95 Latency: 234ms (target: 500ms) ✓                   │
│     Error Budget: 35% remaining                            │
│                                                             │
│  📊 Request Rate (last 1h)                                 │
│     ┌─────────────────────────────────────────┐            │
│     │     ░░░░░░░░░░░░░░░░░░░░░░░░░░         │            │
│     └─────────────────────────────────────────┘            │
│                                                             │
│  📊 Error Rate (last 1h)                                   │
│     ┌─────────────────────────────────────────┐            │
│     │     ░░░░░░░░░░░░░░░░░                   │            │
│     └─────────────────────────────────────────┘            │
│                                                             │
│  🔴 Active Incidents: 2                                    │
│     - P1: High error rate in payment-service               │
│     - P2: Elevated latency in order-service                │
└─────────────────────────────────────────────────────────────┘
```

---

## Four Key Dashboards

### 1. SLO Dashboard (Primary)

Shows: Are we meeting our commitments?

| Panel | Query | Purpose |
|-------|-------|---------|
| Availability | `1 - (5xx / total)` | SLO status |
| p95 Latency | `histogram_quantile(0.95, ...)` | Latency SLO |
| Error Budget | `(remaining / period) * 100` | Budget % |
| Burn Rate | `actual / allowed error rate` | How fast burning |

### 2. Service Health Dashboard

Shows: Is each service healthy?

| Panel | Query | Purpose |
|-------|-------|---------|
| Request Rate | `rate(http_requests_total[5m])` | Traffic |
| Error Rate | `rate(http_errors_total[5m]) / rate(http_requests_total[5m])` | Errors |
| p95 Latency | `histogram_quantile(0.95, http_duration...)` | Speed |
| Saturation | `cpu_usage_percent`, `memory_usage` | Resource pressure |

### 3. Incident Dashboard

Shows: What do I need to fix NOW?

| Panel | Query | Purpose |
|-------|-------|---------|
| Active Alerts | `ALERTS{alertstate="firing"}` | What's broken |
| Recent Incidents | Incident table | Post-mortem context |
| On-Call | Who is currently on-call | Who to page |

### 4. Business Dashboard

Shows: How is the business performing?

| Panel | Query | Purpose |
|-------|-------|---------|
| Orders/Minute | `rate(orders_created[1m])` | Business volume |
| Revenue/Hour | Revenue calculation | Money |
| Active Users | `count_distinct(user_id)` | Usage |

---

## Dashboard Best Practices

```
✅ DO:
   - One dashboard = one purpose
   - Show relevant time range (1h, 24h, 7d)
   - Use consistent colors (green=good, red=bad)
   - Include SLO targets as reference lines
   - Show the "why" (annotations for deployments)

❌ DON'T:
   - Put everything on one dashboard
   - Show more than 6-8 panels (information overload)
   - Use raw metric names (use human-readable labels)
   - Ignore context (no time range, no service names)
```

---

## Dashboard Annotations

Add context to your dashboards:

```yaml
# Grafana annotation for deployments
- Deployment to prod at 2024-01-15 14:30:00
  Service: order-service
  Version: v2.3.1
  Deployed by: alice

# Now when you see a spike, you know:
# "Oh, that's when we deployed v2.3.1"
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's wrong with "monitoring vomit"? (Too much info, no focus)
2. What are the 4 key dashboard types? (SLO, Service, Incident, Business)
3. Why use annotations? (Context for spikes/dips)
4. How many panels per dashboard? (6-8 max)

---

**Ready for the complete solution? Read `step-10.md`**
