# Step 2: Implementing SLOs

---

## Correct Prometheus Queries

```promql
# Request-based SLI (success rate)
sum(rate(http_requests_total{status!~"5.."}[1d]))
/
sum(rate(http_requests_total[1d]))

# Time-based SLI (uptime)
avg_over_time(up[1d])

# P95 latency
histogram_quantile(0.95,
  sum(rate(http_request_duration_seconds_bucket[1d])) by (le)
)
```

---

## Error Budget Tracking

```promql
# Budget remaining
(1 - 0.999)  # Target
-
(1 - sum(rate(http_requests_total{status!~"5.."}[30d]))
       / sum(rate(http_requests_total[30d])))

# Burn rate (actual / allowed daily)
actual_failure_rate / (allowed_failure_rate / 30)
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's the PromQL for success rate? (sum(rate(http_requests_total{status!~"5.."}[1d])) / sum(rate(http_requests_total[1d])))
2. What does status!~"5.." mean? (Status codes NOT matching 5xx - filter out server errors)
3. What's avg_over_time(up[1d])? (Average uptime over 1 day for time-based SLO)
4. What's histogram_quantile(0.95, ...)? (Calculates 95th percentile latency from histogram buckets)
5. How do you calculate burn rate? (actual_failure_rate / (allowed_failure_rate / period))

---

**Read `solution.md`**
