---
name: des-004-observability-design
description: System design problem
difficulty: Advanced
category: Design Review / Observability / Staff Engineer
level: Staff Engineer
---
# Design Review 004: Observability Design Review

---

## The Design Document

```
# Observability Plan

Metrics:
- Prometheus for all services
- Default 15s scrape interval
- Counter for requests, Gauge for memory
- No histograms planned

Logging:
- JSON logs to stdout
- Log levels: ERROR only (to save storage)
- No structured fields planned

Tracing:
- Not included in initial phase
- "Will add later"

Alerting:
- CPU > 80%
- Memory > 80%
- Any 5xx error
```

---

## Your Review

Identify observability gaps.

---

## Concerns

1. **No tracing**: How to debug slow requests?

2. **ERROR only logs**: Can't investigate issues before errors

3. **No histograms**: Latency distribution unknown

4. **Scrape interval**: 15s might miss spikes

5. **No SLOs**: What defines "healthy"?

6. **No context**: Logs without request IDs

---

**Read `step-01.md`
