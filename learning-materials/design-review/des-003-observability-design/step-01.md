# Step 01: The Three Pillars

---

## Question 1: What's Missing?

Look at the proposed design again:

```
Current:
- Prometheus (metrics) ✓
- ELK (logs) ✓
- Grafana (dashboards) ✓
- Distributed tracing ✗

```

**What does tracing give us that metrics and logs don't?**

Think about this scenario:
- Metrics show: "Error rate is up 5%!"
- Logs show: "500 errors in OrderService"
- But you still don't know: **Which requests failed? Which user is affected? Where exactly did it fail?**

**Answer:** Tracing connects the dots across services.

---

## How the Three Pillars Work Together

```
User reports: "My order #123 failed!"

┌─────────────────────────────────────────────────────────────────┐
│                    INVESTIGATION FLOW                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1️⃣  METRICS (The "What")                                        │
│     "Error rate increased from 0.1% to 5% at 14:32 UTC"         │
│     → You know WHEN something happened                         │
│                                                                  │
│  2️⃣  LOGS (The "Why")                                            │
│     grep "order-123" logs/*                                     │
│     "Payment declined: card expired at line 42"                 │
│     → You know WHAT error occurred                              │
│                                                                  │
│  ❌ WITHOUT TRACING:                                            │
│     "Which service? Which endpoint? What was the full path?"    │
│     → You're stuck grep-ing multiple services                   │
│                                                                  │
│  3️⃣  TRACES (The "Where")                                        │
│     trace_id=abc123 shows:                                      │
│     API Gateway → Auth → Order → Payment → Inventory           │
│     💥 Failed at Payment (234ms)                                │
│     → You see the FULL journey                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## The Missing Piece: Distributed Tracing

A trace represents **one request's journey** through your system.

```
Trace for: GET /api/orders/123

┌─────────────────────────────────────────────────────────────┐
│  API Gateway (50ms)                                         │
│  └─▶ Auth Service (10ms)                                    │
│  └─▶ Order Service (30ms)                                   │
│      └─▶ Database Query (25ms)                              │
│  └─▶ Inventory Service (10ms)                               │
│                                                             │
│  Total: 50ms                                                 │
│  💡 Shows exactly where time was spent                      │
└─────────────────────────────────────────────────────────────┘
```

**Without tracing:** You know the API is slow, but not why.
**With tracing:** You see that the database query is the bottleneck.

---

## Key Insight

Each pillar answers a different question:

| Pillar | Answers | Example |
|--------|---------|---------|
| **Metrics** | "Is something wrong?" | Error rate: 5% (normally 0.1%) |
| **Logs** | "What happened?" | "Payment declined: card expired" |
| **Traces** | "Where did it happen?" | Failed at Payment Service, step 3 of 5 |

**You need all three** to quickly diagnose issues in distributed systems.

---

## Quick Check

Before moving on, make sure you understand:

1. Why aren't metrics enough? (Think: they're aggregated)
2. Why aren't logs enough? (Think: they're siloed per service)
3. What does tracing add? (Think: request-level context)

---

**Ready to fix the metrics problem? Read `step-02.md`**
