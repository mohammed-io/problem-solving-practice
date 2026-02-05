# Solution: SLO Implementation

---

## Root Cause

Dashboard used `[1h]` query instead of `[1d]`, showing only recent performance.

---

## Solution

**Correct SLI dashboard:**

```python
import datetime
from prometheus_api import PrometheusApi

class SLODashboard:
    def __init__(self, prometheus: PrometheusApi, slo_target: float = 0.999):
        self.prometheus = prometheus
        self.slo_target = slo_target

    def get_daily_sli(self, date: datetime.date) -> dict:
        """Calculate SLI for full day."""
        start = datetime.datetime.combine(date, datetime.time.min)
        end = datetime.datetime.combine(date, datetime.time.max)

        # Use full day range, not extrapolated hour
        query = '''
            sum(rate(http_requests_total{status!~"5.."}[1d]))
            /
            sum(rate(http_requests_total[1d]))
        '''

        result = self.prometheus.query_range(query, start, end)
        sli = float(result[0]['value'][1])

        return {
            'date': date.isoformat(),
            'sli': sli,
            'target': self.slo_target,
            'compliant': sli >= self.slo_target,
            'budget_consumed': (1 - sli) / (1 - self.slo_target),
        }
```

**Error budget alert:**

```yaml
groups:
  - name: error_budget
    interval: 1m
    rules:
      - alert: ErrorBudgetBurn
        expr: |
          (1 - sum(rate(http_requests_total{status!~"5.."}[1h]))
                / sum(rate(http_requests_total[1h])))
          / ((1 - 0.999) / 30 / 24) > 10
        for: 5m
        annotations:
          summary: "Error budget burning 10x faster than allowed"
```

---

**Next Problem:** `observability/obs-104-alert-fatigue/`
