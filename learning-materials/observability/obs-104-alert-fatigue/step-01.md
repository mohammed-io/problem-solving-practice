# Step 1: Alert Design Principles

---

## Actionable Alerts Only

**The test: "If this alert fires at 3 AM, what will I do?"**

| Alert | Actionable? | Why |
|-------|-------------|-----|
| CPU > 90% for 5m | Maybe | Depends: Is it causing user impact? |
| API error rate > 1% | Yes | Restart service, rollback deploy |
| Disk < 10% | Yes | Clear logs, expand disk |
| Pod not ready | Maybe | Is there spare capacity? |
| CPU > 50% | No | Normal for many servers |

**Better: Alert on symptoms, not causes:**

```promql
# BAD: Alert on CPU
cpu_usage_percent > 90

# GOOD: Alert on latency (user symptom)
http_request_duration_seconds{quantile="0.95"} > 0.5

# CPU may be diagnostic data, not alert
```

---

## Severity Framework

**P1 - Critical (wake someone up):**
- Service down for all users
- Data loss occurring
- Security breach in progress

**P2 - High (respond within 15 min):**
- Service degraded for significant users
- Feature broken for specific segment
- Performance severely degraded

**P3 - Medium (respond within 1 hour):**
- Single non-critical service affected
- Automated fix available
- Low-traffic feature broken

**P4 - Low (next business day):**
- Dashboard incorrect
- Non-urgent config needed
- Documentation issue

---

## Threshold Guidelines

**Use percentiles, not averages:**

```promql
# BAD: Average latency
rate(http_request_duration_seconds_sum[5m])
/
rate(http_request_duration_seconds_count[5m])

# GOOD: P95 latency
histogram_quantile(0.95,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
)
```

**Set duration to avoid blips:**

```yaml
# BAD: Alerts on spikes
expr: error_rate > 0.01
for: 1m

# GOOD: Requires sustained issue
expr: error_rate > 0.01
for: 5m
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's the actionable alert test? ("If this alert fires at 3 AM, what will I do?" - if nothing, don't page)
2. Why alert on symptoms not causes? (Causes like high CPU may not impact users; symptoms like latency do)
3. What's P1 severity? (Critical - wake someone up, service down for all users)
4. Why use P95 instead of average latency? (Average hides outliers, P95 shows what most users experience)
5. What's the `for` duration in alerts? (Sustained threshold time to avoid alerting on blips)

---

**Read `step-02.md`**
