# Solution: Alert Strategy

---

## Root Cause

Too many alerts with low thresholds, short durations, and no actionability caused alert fatigue.

---

## Solution

**Alert framework:**

```yaml
groups:
  - name: critical_alerts
    rules:
      # User-facing symptoms only
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m]))
          /
          sum(rate(http_requests_total[5m])) > 0.01
        for: 5m
        labels:
          severity: P1
          runbook: https://runbooks/high-error-rate
        annotations:
          summary: "Error rate above 1% for 5 minutes"
          action: "Check recent deploys, database status"

      - alert: HighLatency
        expr: |
          histogram_quantile(0.95,
            sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
          ) > 0.5
        for: 5m
        labels:
          severity: P1
        annotations:
          summary: "P95 latency above 500ms"
          action: "Check CPU, memory, database queries"

  - name: warning_alerts
    rules:
      # Potential issues, not pages
      - alert: DiskSpaceWarning
        expr: disk_free_percent < 20
        for: 15m
        labels:
          severity: P3
          alert_type: ticket  # Not page!
        annotations:
          summary: "Disk space below 20%"
          action: "Plan disk cleanup in next sprint"
```

**Alert quality metrics:**

```python
class AlertMetrics:
    def __init__(self):
        self.alerts_per_week = 0
        self.actionable_alerts = 0
        self.false_positives = 0

    def alert_signal_ratio(self) -> float:
        """Signal = actionable alerts, Noise = false positives"""
        total = self.actionable_alerts + self.false_positives
        if total == 0:
            return 0
        return self.actionable_alerts / total

    # Target: Signal ratio > 0.7
    # If below 0.5: Need alert cleanup
```

---

## Quick Checklist

**Before adding an alert:**
- [ ] What action will be taken?
- [ ] Is severity appropriate (P1-P4)?
- [ ] Has runbook been written?
- [ ] Is threshold based on user symptoms?
- [ ] Will this page someone or create ticket?
- [ ] Reviewed for potential false positives?

**Quarterly:**
- [ ] Review all alerts for necessity
- [ ] Delete unused alerts
- [ ] Convert pages to tickets where appropriate
- [ ] Update runbooks

---

**Next Problem:** `security/sec-101-secret-rotation/`
