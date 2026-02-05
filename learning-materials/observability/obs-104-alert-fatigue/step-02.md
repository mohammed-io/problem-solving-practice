# Step 2: Alert Governance

---

## Alert Audit Process

**Quarterly alert review:**

```
For each alert:
1. When did it last fire?
2. What action was taken?
3. Was the action useful?
4. Can it be deleted or converted to ticket?

If answer to #3 is "no" → delete alert
If action isn't urgent → convert to ticket
```

**Alert inventory template:**

```python
@dataclass
class AlertDefinition:
    name: str
    query: str
    severity: str  # P1, P2, P3, P4
    last_fired: datetime
    fires_per_month: int
    actionable: bool
    runbook_url: str

    def should_alert(self) -> bool:
        """Returns True if this should page, False if should be ticket."""
        return self.severity in ['P1', 'P2'] and self.actionable
```

---

## Noise Reduction Techniques

**1. Hysteresis (different up/down thresholds):**

```yaml
# Alert fires at 90%, clears at 70%
- alert: HighCPU
  expr: cpu_usage_percent > 90
  annotations:
    clears_at: cpu_usage_percent < 70
```

**2. Suppress during maintenance:**

```yaml
# Don't alert during known windows
- alert: HighCPU
  expr: cpu_usage_percent > 90
  unless: maintenance_window_active == 1
```

**3. Aggregate similar alerts:**

```yaml
# Instead of one alert per pod
- alert: HighCPUMultiplePods
  expr: count(cpu_usage_percent > 90) > 3
  annotations:
    summary: "High CPU on {{ $value }} pods"
```

**4. Rate limiting:**

```yaml
# Only alert once per hour per unique issue
- alert: DiskSpaceLow
  expr: disk_free_percent < 10
  for: 5m
  labels:
    throttle_rate: 1h
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's an alert audit? (Quarterly review of all alerts to assess actionability and usefulness)
2. What should happen if an alert isn't actionable? (Delete it or convert to ticket)
3. What's hysteresis? (Different thresholds for firing and clearing, prevents flapping)
4. What's alert aggregation? (Combine similar alerts into one to reduce noise)
5. What's maintenance window suppression? (Don't alert during known maintenance periods)

---

**Read `solution.md`**
