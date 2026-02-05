# Step 10: Putting It All Together

---

## Summary: Complete Observability Strategy

You've learned the key components. Now let's design the complete solution.

---

## The Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY PLATFORM                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐    │
│  │   METRICS      │  │     LOGS       │  │    TRACES     │    │
│  │  (Prometheus)  │  │    (Loki/ELK)  │  │   (Jaeger)     │    │
│  │                │  │                │  │                │    │
│  │ • RED method   │  │ • Structured   │  │ • Spans        │    │
│  │ • Low cardinality│  │ • Trace ID    │  │ • Context prop │    │
│  └────────────────┘  └────────────────┘  └────────────────┘    │
│          │                  │                  │                │
│          └──────────────────┴──────────────────┘                │
│                             │                                   │
│                    ┌────────▼────────┐                          │
│                    │   Grafana       │                          │
│                    │   (Dashboards)  │                          │
│                    └─────────────────┘                          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              ALERT MANAGER (Prometheus)                   │  │
│  │                                                           │  │
│  │  • SLO-based alerts (burn rate)                           │  │
│  │  • Multi-condition (threshold + duration + volume)        │  │
│  │  • Severity levels (P1-P4)                                │  │
│  │  • Runbook links                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                            ▲
                            │
        ┌───────────────────┴───────────────────┐
        │                                           │
   ┌────▼────┐  ┌─────────┐  ┌─────────┐  ┌────▼────┐
   │Service A│  │Service B│  │Service C│  │Service D│
   └─────────┘  └─────────┘  └─────────┘  └─────────┘
```

---

## Implementation Checklist

### Phase 1: Foundation (Week 1-2)

- [ ] Set up Prometheus for metrics collection
- [ ] Implement RED method metrics (3 per service)
- [ ] Set up Loki/ELK for centralized logging
- [ ] Implement structured logging with trace IDs
- [ ] Create basic Grafana dashboards

### Phase 2: Tracing (Week 3-4)

- [ ] Set up Jaeger or Tempo for tracing
- [ ] Instrument services with OpenTelemetry
- [ ] Implement context propagation
- [ ] Create trace-based dashboards

### Phase 3: SLOs and Alerting (Week 5-6)

- [ ] Define SLIs for each service
- [ ] Set SLO targets based on user requirements
- [ ] Implement error budget tracking
- [ ] Create SLO-based alerts (burn rate)
- [ ] Remove old threshold-based alerts
- [ ] Document runbooks for each alert

### Phase 4: Operational Excellence (Ongoing)

- [ ] Regular SLO review (monthly)
- [ ] Alert fatigue reduction (quarterly)
- [ ] Dashboard cleanup (quarterly)
- [ ] On-call training (ongoing)

---

## Sample: Complete Service Implementation

```go
package main

import (
    "context"
    "net/http"

    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promauto"
    "go.opentelemetry.io/otel"
    "go.uber.org/zap"
)

// All observability in one place
type ObservableService struct {
    logger *zap.Logger
    tracer trace.Tracer
    metrics *ServiceMetrics
}

type ServiceMetrics struct {
    Requests  *prometheus.CounterVec
    Errors    *prometheus.CounterVec
    Duration  *prometheus.HistogramVec
}

func NewObservableService(serviceName string) *ObservableService {
    logger := NewLogger(serviceName)
    tracer := NewTracer(serviceName)
    metrics := NewMetrics(serviceName)

    return &ObservableService{
        logger:  logger,
        tracer:  tracer,
        metrics: metrics,
    }
}

func (s *ObservableService) HandleRequest(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()
    start := time.Now()

    // 1. Start trace span
    ctx, span := s.tracer.Start(ctx, "HandleRequest")
    defer span.End()

    // 2. Add structured logging with trace context
    s.logger.Info(ctx, "handling_request",
        zap.String("path", r.URL.Path),
        zap.String("method", r.Method),
    )

    // 3. Handle request
    status, err := s.process(ctx, r)

    // 4. Record error in trace
    if err != nil {
        span.RecordError(err)
        s.logger.Error(ctx, "request_failed",
            zap.Error(err),
            zap.Int("status", status),
        )
    } else {
        s.logger.Info(ctx, "request_completed",
            zap.Int("status", status),
        )
    }

    // 5. Record metrics
    duration := time.Since(start)
    s.metrics.RecordRequest("order-api", r.Method, r.URL.Path, status, duration)

    w.WriteHeader(status)
}
```

---

## Key Takeaways

| Concern | Before | After |
|---------|--------|-------|
| **Metrics** | 500+ per service, explosion | 3-4 per service (RED) |
| **Alerts** | CPU > 80%, noisy | SLO burn rate, actionable |
| **Logs** | Unstructured, grep hell | Structured, queryable |
| **Traces** | None | Full request journeys |
| **SLOs** | Undefined | Clear targets with budgets |
| **Dashboards** | Monitoring vomit | Purpose-built, focused |

---

## The Goal

Move from "Dark" (Level 0) to "SLO-Driven" (Level 4):

```
Level 0 (Dark):      "Users tell us when it's down"
         ↓
Level 1 (Metrics):   "CPU is high, something might be wrong"
         ↓
Level 2 (Logs):      "Error logs are increasing"
         ↓
Level 3 (Traces):    "We can see where requests fail"
         ↓
Level 4 (SLOs):      "We know when user experience is degraded"
```

---

## Final Review

Before implementing, ask yourself:

1. [ ] Can I answer "Is the system healthy?" in 5 seconds?
2. [ ] When an alert fires, do I know what to do?
3. [ ] Can I trace a single request through all services?
4. [ ] Are my SLOs based on user expectations?
5. [ ] Is my on-call team getting <5 pages/week?

**If yes to all, you have a solid observability strategy.**

---

**Ready for implementation details? Read `solution.md`**
