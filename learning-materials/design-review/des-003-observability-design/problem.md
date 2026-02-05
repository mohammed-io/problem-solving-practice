---
category: Design Review
description: Designing observability strategy for distributed systems - metrics, logs,
  traces, dashboards, and alerting
difficulty: Advanced
level: Principal Engineer
name: des-003-observability-design
---

# Design Review 003: Observability Strategy

## The Situation

You're reviewing the observability design for a microservices application. The current team proposed:

```
                    ┌─────────────────────────────────────┐
                    │     Observability Platform          │
                    ├─────────────────────────────────────┤
                    │  ┌─────────┐  ┌─────────┐          │
                    │  │ Metrics │  │  Logs   │          │
                    │  │ (Prom.) │  │ (ELK)   │          │
                    │  └────┬────┘  └────┬────┘          │
                    │       │            │                │
                    │  ┌────▼────────────▼────┐          │
                    │  │     Grafana          │          │
                    │  │    (Dashboards)      │          │
                    │  └──────────────────────┘          │
                    └─────────────────────────────────────┘
                           ▲            ▲
                           │            │
        ┌──────────────────┴────────────┴──────────────────┐
        │                                                  │
   ┌────▼────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
   │Service A│  │Service B│  │Service C│  │Service D│
   └─────────┘  └─────────┘  └─────────┘  └─────────┘
```

**The proposed design:**
- Push metrics to Prometheus every 15 seconds
- Send logs to ELK stack
- No distributed tracing
- Alert on: CPU > 80%, Memory > 80%, Error rate > 5%

---

## The Challenge

The current design has several problems:

```
❌ No distributed tracing:
- Request spans 5 services, where is it slow?
- Which service is causing the 500 errors?
- "It works on my machine" - but where does it fail?

❌ Metrics are too granular:
- Every service exports 500+ metrics
- Metric explosion: 50 services × 500 metrics = 25,000 time series
- Prometheus is struggling to scrape

❌ Logs are unstructured:
- Free-form text logs
- No correlation IDs
- Can't query "all logs for request #123"

❌ Alerts are noisy:
- CPU > 80% fires constantly (brief spikes)
- Error rate > 5% triggers during deployments
- On-call team gets paged 20+ times/night
- Alert fatigue → real incidents ignored

❌ No SLO/SLI:
- No defined service level objectives
- Can't answer "is the system healthy?"
- Don't know if we're meeting user expectations
```

---

## Your Task

**As a Principal Engineer reviewing this design:**

1. **What's missing from the observability strategy?** (Hint: three pillars of observability)

2. **How do you fix the metric explosion problem?** What metrics should actually be collected?

3. **How do you reduce alert fatigue?** What makes a good alert vs. bad alert?

4. **Design a proper SLO/SLI strategy.** What service level objectives matter?

5. **How do you add distributed tracing?** What should you trace?

---

## Key Concepts

**Observability:** The ability to understand a system's internal state by examining its outputs. Three pillars: Metrics, Logs, Traces.

**Metrics:** Numeric time-series data. Good for: trends, aggregates, alerting. Bad for: "why did this happen?"

**Logs:** Discrete events with context. Good for: debugging, audit trails. Bad for: trends, high-cardinality data.

**Traces:** Request path through distributed systems. Good for: latency analysis, dependency mapping. Bad for: long-term retention (expensive).

**SLI (Service Level Indicator):** A measured metric of service behavior. Example: "95th percentile latency"

**SLO (Service Level Objective):** A target value for an SLI. Example: "95th percentile latency < 200ms"

**SLA (Service Level Agreement):** A business contract with consequences. Example: "99.9% uptime or 10% credit"

**Red/Metrics:** The four golden signals: Latency, Traffic, Errors, Saturation.

**USE Method:** For resources: Utilization, Saturation, Errors.

**RED Method:** For services: Rate, Errors, Duration.

**Cardinality:** Number of unique time series. High cardinality = expensive. Example: `user_id` label = very high cardinality.

**Correlation ID:** Unique identifier attached to a request, propagated across services. Links logs/traces.

**Span:** A single operation in a distributed trace. Has start time, duration, tags.

**Trace:** A tree of spans representing a request's path through the system.

---

## Visual: Three Pillars of Observability

```
                    THREE PILLARS OF OBSERVABILITY

     ┌───────────────────────────────────────────────────────────────┐
     │                                                               │
     │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
     │  │   METRICS   │  │    LOGS     │  │   TRACES    │          │
     │  │             │  │             │  │             │          │
     │  │ • Numeric   │  │ • Events    │  │ • Request   │          │
     │  │ • Time-series│  │ • Text      │  │   paths     │          │
     │  │ • Aggregated│  │ • Discrete  │  │ • Spans     │          │
     │  │ • Low-card  │  │ • Detailed  │  │ • Tree      │          │
     │  │             │  │             │  │             │          │
     │  │ "WHAT?"     │  │ "WHY?"      │  │ "WHERE?"    │          │
     │  │             │  │             │  │             │          │
     │  │ Questions:  │  │ Questions:  │  │ Questions:  │          │
     │  │ • Is X up?  │  │ • What      │  │ • Where is  │          │
     │  │ • Trending? │  │   happened? │  │   it slow?  │          │
     │  │ • Alerts?   │  │ • Error     │  │ • Which     │          │
     │  │             │  │   context?  │  │   services? │          │
     │  └─────────────┘  └─────────────┘  └─────────────┘          │
     │                                                               │
     └───────────────────────────────────────────────────────────────┘

     ┌───────────────────────────────────────────────────────────────┐
     │                    HOW THEY WORK TOGETHER                    │
     │                                                               │
     │  1. METRICS alert you: "Error rate increased!"               │
     │  2. LOGS show details: "NullPointerException at Line 42"     │
     │  3. TRACES show path: "Service A → B → C (slow at B)"        │
     │                                                               │
     └───────────────────────────────────────────────────────────────┘
```

---

## Visual: From Bad Alert to Good Alert

### Bad Alert (Noisy)

```
┌─────────────────────────────────────────────────────────────┐
│ ALERT: cpu_usage_high                                      │
│ Condition: cpu > 80%                                       │
│                                                             │
│ Fires: Daily (during normal spikes)                        │
│ Action: "Check CPU" (but what can you do?)                 │
│ Result: Ignored → real incident missed                    │
└─────────────────────────────────────────────────────────────┘
```

### Good Alert (Actionable)

```
┌─────────────────────────────────────────────────────────────┐
│ ALERT: high_error_rate_impacting_users                     │
│ Condition:                                                   │
│   - 5xx rate > 1% for 5 minutes                            │
│   - AND impacting > 1000 users/minute                      │
│   - AND SLO budget burn rate > 10× normal                  │
│                                                             │
│ Severity: P1 - System degradation                          │
│ Runbook: https://runbooks.dev/high-error-rate              │
│                                                             │
│ Fires: Monthly (real issues)                               │
│ Action: Rollback deployment, scale up, investigate          │
│ Result: Taken seriously, fast response                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Visual: Distributed Trace Example

```
Request: GET /api/orders/123

┌─────────────────────────────────────────────────────────────────┐
│  Trace ID: 7a3f2c1b-e8d4-4f5a-9b6c-3d2e1f4a5b6c                 │
│  Total Duration: 847ms                                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ Span 1: API Gateway                                     │    │
│  │ Duration: 847ms (100%)                                  │    │
│  │ Tags: method=GET, path=/api/orders/123, status=200      │    │
│  │                                                          │    │
│  │  ┌──────────────────────────────────────────────┐      │    │
│  │  │ Span 2: Auth Service                          │      │    │
│  │  │ Duration: 45ms (5%)                           │      │    │
│  │  │ Tags: token_valid=true, user_id=12345         │      │    │
│  │  └──────────────────────────────────────────────┘      │    │
│  │                                                          │    │
│  │  ┌──────────────────────────────────────────────────┐  │    │
│  │  │ Span 3: Order Service                            │  │    │
│  │  │ Duration: 795ms (94%) ⚠️ SLOW                    │  │    │
│  │  │ Tags: db_query=SELECT * FROM orders...            │  │    │
│  │  │                                                   │  │    │
│  │  │  ┌─────────────────────────────────────────┐    │  │    │
│  │  │  │ Span 3.1: Cache (MISS)                  │    │  │    │
│  │  │  │ Duration: 5ms                            │    │  │    │
│  │  │  └─────────────────────────────────────────┘    │  │    │
│  │  │                                                   │  │    │
│  │  │  ┌─────────────────────────────────────────┐    │  │    │
│  │  │  │ Span 3.2: Database Query (SLOW!)        │    │  │    │
│  │  │  │ Duration: 785ms ⚠️                       │    │  │    │
│  │  │  │ Tags: query=SELECT *, rows=1, index_hit=0 │  │  │    │
│  │  │  │                                            │  │    │
│  │  │  │  ⚠️ FULL TABLE SCAN - NO INDEX USED       │  │  │    │
│  │  │  └─────────────────────────────────────────┘    │  │    │
│  │  └──────────────────────────────────────────────────┘  │    │
│  │                                                          │    │
│  │  ┌──────────────────────────────────────────────┐      │    │
│  │  │ Span 4: Inventory Service                     │      │    │
│  │  │ Duration: 15ms (2%)                           │      │    │
│  │  └──────────────────────────────────────────────┘      │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

INSIGHT: Database query is slow (785ms). Full table scan detected.
ACTION: Add index on orders.id column.
```

---

## Observability Maturity Model

| Level | Name | Characteristics |
|-------|------|------------------|
| **0** | Dark | No monitoring. "Users tell us when it's down" |
| **1** | Metrics Only | Basic metrics (CPU, memory). No logs/traces. "Something is slow" |
| **2** | Metrics + Logs | Can answer "what happened" but not "where" |
| **3** | Three Pillars | Metrics + Logs + Traces. Full observability |
| **4** | SLO-Driven | SLOs defined, budget tracked, alert on SLO burn |
| **5** | Proactive | Predictive alerting, anomaly detection, auto-remediation |

**Most companies:** Level 2-3
**Goal:** Level 4 (SLO-driven)

---

## Questions to Consider

1. **How much is observability costing you?** Compute: storage + compute + alerting
2. **What's your MTTR (Mean Time To Recover)?** Can observability reduce it?
3. **Who is your observability for?** Developers? SREs? Product? Executives?
4. **What's your retention policy?** 7 days? 30 days? 1 year? Why?
5. **How do you onboard new services?** Is observability automated or manual?

---

---

## Learning Path

This problem has **10 progressive steps** that will guide you through:

1. **Step 01** - The Three Pillars (Metrics, Logs, Traces)
2. **Step 02** - The Metrics Explosion Problem
3. **Step 03** - Why Alerts Fail
4. **Step 04** - Multi-Condition Alerting
5. **Step 05** - Understanding SLOs and SLIs
6. **Step 06** - SLO-Based Alerting
7. **Step 07** - Distributed Tracing Implementation
8. **Step 08** - Structured Logging
9. **Step 09** - Building Effective Dashboards
10. **Step 10** - Putting It All Together

Each step builds on the previous one. Work through them in order.

---

**When you've thought about it, read `step-01.md`**
