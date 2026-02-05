# Step 06: SLO-Based Alerting

---

## The Problem

Most teams alert on **thresholds**, not SLOs:

```
❌ Traditional alerting:
   - latency > 1s
   - error_rate > 5%
   - cpu > 80%

   Problem: These numbers are arbitrary!
   Why 1s? Why 5%? Why 80%?
   Do they matter to users?
```

---

## Solution: Alert on Error Budget Burn

Instead of alerting on absolute thresholds, alert when **you're burning through your error budget too fast**.

```
┌─────────────────────────────────────────────────────────────┐
│                    ERROR BUDGET OVER TIME                   │
│                                                             │
│  100% ████████████████████████████████████████████        │
│   75% ████████████████████████████████                    │
│   50% ██████████████████████                               │
│   25% ██████████████                                       │
│    0%                                                      │
│         └─────────────────────────────────────► time      │
│                    ▲                                       │
│                    └── Alert here! Not at 80% CPU           │
└─────────────────────────────────────────────────────────────┘
```

---

## Burn Rate Alert Levels

| Burn Rate | Meaning | Alert Action | Time to Exhaust Budget |
|-----------|---------|--------------|------------------------|
| **1x** | Normal | None | 30 days (full period) |
| **2x** | Elevated | Warning ticket | 15 days |
| **10x** | High | Page team | 3 days |
| **100x** | Critical | Wake everyone up | 7 hours! |

---

## Implementation: Calculating Error Budget

```go
package slo

import "time"

// ErrorBudget tracks SLO compliance
type ErrorBudget struct {
    TargetPercent    float64     // e.g., 99.9
    Period           time.Duration // e.g., 30 days

    // Calculated
    totalRequests    float64
    badRequests      float64
}

func (eb *ErrorBudget) Availability() float64 {
    if eb.totalRequests == 0 {
        return 100
    }
    return 100 * (1 - eb.badRequests/eb.totalRequests)
}

func (eb *ErrorBudget) BudgetRemaining() float64 {
    allowedErrorRate := (100 - eb.TargetPercent) / 100
    actualErrorRate := eb.badRequests / eb.totalRequests

    if actualErrorRate == 0 {
        return 100
    }

    burnRate := actualErrorRate / allowedErrorRate
    return 100 - (burnRate * 100)
}

func (eb *ErrorBudget) BurnRate() float64 {
    allowedErrorRate := (100 - eb.TargetPercent) / 100
    actualErrorRate := eb.badRequests / eb.totalRequests
    return actualErrorRate / allowedErrorRate
}

func (eb *ErrorBudget) TimeToExhaust() time.Duration {
    burnRate := eb.BurnRate()
    if burnRate <= 1 {
        return time.Duration(1<<63 - 1) // Infinite
    }
    return time.Duration(float64(eb.Period) / burnRate)
}
```

---

## Alerting on Burn Rate

```yaml
groups:
  - name: slo_based_alerts
    interval: 1m
    rules:
      # WARNING: 2x burn rate
      - alert: SLOBudgetBurningFast
        expr: slo_burn_rate > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "SLO budget burning at {{ $value }}x normal rate"
          description: "At this rate, budget will be exhausted in {{ $value | humanizeDuration }}"

      # CRITICAL: 10x burn rate
      - alert: SLOBudgetCritical
        expr: slo_burn_rate > 10
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "SLO budget burning at {{ $value }}x normal rate!"
          description: "At this rate, budget will be exhausted in {{ $value | humanizeDuration }}"
          runbook: "https://runbooks.dev/slo-burn-critical"
          action: "Rollback deployment or scale immediately"

      # SEVERE: Budget exhausted
      - alert: SLOBreached
        expr: slo_budget_remaining < 0
        for: 1m
        labels:
          severity: severe
        annotations:
          summary: "SLO BREACHED - No budget remaining"
          action: "Stop all releases until budget recovers"
```

---

## Why This Works

**Traditional alert:** `latency > 1s`
- Fires when latency spikes... even if SLO is still met
- Or doesn't fire when latency is high but within SLO

**SLO-based alert:** `budget_burn_rate > 10x`
- Only fires when users are actually affected
- Accounts for current vs normal error rate
- Directly tied to business impact

---

## Quick Check

Before moving on, make sure you understand:

1. Why alert on burn rate instead of thresholds? (Direct user impact)
2. What burn rate should trigger a P1 alert? (10x or higher)
3. What happens when budget is exhausted? (Stop releases)
4. How is burn rate calculated? (actual / allowed error rate)

---

**Ready to add distributed tracing? Read `step-07.md`**
