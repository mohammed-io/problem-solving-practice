# Step 04: Multi-Condition Alerting

---

## The Problem

Single-condition alerts are too noisy:

```
❌ error_rate > 5%
   → Fires during deployments (expected errors)
   → Fires when 1 request fails (not significant)

❌ latency > 1s
   → Fires during brief spikes
   → Fires for low-traffic endpoints
```

---

## Solution: Combine Multiple Conditions

A good alert has **all of these**:

1. **Severity threshold** - "How bad is it?"
2. **Duration** - "How long has it been bad?"
3. **Volume threshold** - "How many users are affected?"
4. **Trend check** - "Is it getting worse?"

---

## Example: Building a Good Alert

Start simple, add conditions:

```
Step 1: Too simple
error_rate > 5%
→ Fires too often (deployments, low traffic)

Step 2: Add duration
error_rate > 5% for 5 minutes
→ Better, but still fires during deployments

Step 3: Add volume
error_rate > 5% for 5 minutes
AND requests_per_second > 100
→ Ignores low-traffic endpoints

Step 4: Add trend
error_rate > 5% for 5 minutes
AND requests_per_second > 100
AND error_rate increased > 2x in last 5 minutes
→ Only alerts on sudden degradation, not gradual drift

Step 5: Add SLO context
error_rate > 5% for 5 minutes
AND requests_per_second > 100
AND error_rate increased > 2x in last 5 minutes
AND error_budget_remaining < 25%
→ Only alerts when it actually matters for SLO
```

---

## Prometheus Alert Example

```yaml
# GOOD ALERT: Multiple conditions
groups:
  - name: critical_alerts
    rules:
      - alert: HighErrorRateImpactingUsers
        # Condition 1: Elevated errors for 5 minutes
        expr: |
          rate(http_requests_total{status=~"5.."}[5m])
          / rate(http_requests_total[5m])
          > 0.01
        # Condition 2: Significant traffic
        and rate(http_requests_total[5m]) > 100
        # Condition 3: Burning error budget fast
        and slo_budget_burn_rate > 10

        for: 5m  # Must persist for 5 minutes

        labels:
          severity: critical
          team: platform

        annotations:
          summary: "High error rate impacting users"
          description: "{{ $labels.service }} error rate is {{ $value | humanizePercentage }}"
          runbook: "https://runbooks.dev/high-error-rate"
          impact: "Affecting {{ $value | humanize }} requests/sec"
```

---

## The `for` Clause is Critical

```yaml
# WITHOUT 'for' - fires immediately on blip
- alert: HighLatency
  expr: histogram_quantile(0.95, rate(http_duration_seconds_bucket[5m])) > 0.5
  # Fires on single spike!

# WITH 'for' - only fires if sustained
- alert: HighLatency
  expr: histogram_quantile(0.95, rate(http_duration_seconds_bucket[5m])) > 0.5
  for: 10m  # Must be high for 10 minutes
  # Only fires if problem is real and sustained
```

---

## Alert Severity Levels

Not all alerts should page you:

| Severity | Example | Action |
|----------|---------|--------|
| **P1 - Critical** | SLO breach, service down | Page immediately |
| **P2 - High** | High error rate, latency degradation | Page within 15 min |
| **P3 - Medium** | Elevated errors, low traffic | Ticket + investigate next day |
| **P4 - Low** | Disk filling in 7 days | Ticket only |
| **P5 - Info** | Deployment completed | No action, just notification |

---

## Quick Check

Before moving on, make sure you understand:

1. Why combine multiple conditions? (Reduce false positives)
2. What does the `for` clause do? (Requires sustained condition)
3. What's the difference between P1 and P4 alerts? (Urgency + action)

---

**Ready to learn about SLOs? Read `step-05.md`**
