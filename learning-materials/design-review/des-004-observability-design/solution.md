# Solution: Observability Design

---

## Improved Design

```
# Observability Plan (Improved)

Metrics:
- Counters: requests, errors (by endpoint, status)
- Gauges: active connections, queue depth
- Histograms: request latency, DB query time
- Scrape: 15s normal, 1s for critical

Logging:
- Structured: INFO level with context
- Fields: request_id, user_id, trace_id
- Sampling: DEBUG logs for 1% of requests

Tracing:
- OpenTelemetry for all services
- Propagate context across calls
- Sample rate: 100% for errors, 10% for normal
- Span attributes: user_id, endpoint

Alerting:
- SLO-based: error-budget burn rate
- Latency: P95 > threshold for 5min
- Saturation: queue depth > limit
- Runbook links for all alerts
```

---

## Observability Checklist

**Must Have:**
- [ ] RED metrics (Rate, Errors, Duration)
- [ ] Distributed tracing
- [ ] Structured logging with correlation IDs
- [ ] SLO dashboard
- [ ] Runbooks for alerts

**Should Have:**
- [ ] Profiling integration
- [ ] Synthetic monitoring
- [ ] User journey tracking
- [ ] Cost attribution

---

**Status:** All 26 problems complete!
