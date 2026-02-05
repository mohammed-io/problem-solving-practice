# Step 1: Observability Gaps

---

## Problems

**1. No Tracing**
```
Slow request (5s):
- Which service caused it?
- Which database call?
- Where was time spent?

Without tracing: Guessing game
```

**2. ERROR Only Logs**
```
Investigation scenario:
User reports "order failed"
Logs show ERROR at order service
But: What happened before?
No context, no debugging info
```

**3. No Latency Distribution**
```
Gauge: "current latency"
Histogram: "latency distribution"

P99 latency might be 10x P50
Gauge might show P50 = 10ms (looks good!)
But P99 = 100ms (users complaining!)
```

**4. No SLOs**
```
"CPU > 80%" alert:
- Is this user-impacting?
- What's the target?
- When do we page someone?

Need SLO: "99.9% requests < 100ms"
Then alert on SLO degradation, not metrics
```

---

**Read `solution.md`
