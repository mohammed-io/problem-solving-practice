# Step 1: SLO Calculation Methods

---

## Request-Based vs Time-Based

**Request-Based:** "99.9% of requests succeed"
```
SLI = successful_requests / total_requests
Works for: APIs with discrete requests
```

**Time-Based:** "99.9% of time, service is healthy"
```
SLI = healthy_time / total_time
Works for: Always-on services, background processes
```

**Scenario: 1-hour outage at midnight (low traffic)**
```
Request-based: 1B requests, 100K failed → 99.99% ✓
Time-based: 3600s unhealthy / 86400s → 95.8% ✗

Which is correct? Depends on user impact.
If users affected → time-based more accurate.
```

---

## Rolling vs Calendar Windows

**Rolling (30 days):**
```
Always last 30 days
Pros: Smooth, no sudden drops
Cons: Harder to predict
```

**Calendar (Month):**
```
Fixed period, resets monthly
Pros: Clear periods, easier planning
Cons: Edge-of-period behavior
```

---

## Error Budget Math

```
SLO: 99.9%
Error Budget: 0.1%

Monthly allowance: 43 minutes
Daily allowance: 86 seconds

Burn rate alerting:
  10x normal → Page someone
  100x normal → Major incident
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's request-based SLO? (Percentage of successful requests: successful / total)
2. What's time-based SLO? (Percentage of time service is healthy: healthy_time / total_time)
3. When would time-based be more accurate? (Outage affects users even if low traffic, like midnight batch job)
4. What's error budget? (Allowed failure rate: 100% - SLO, e.g., 99.9% SLO = 0.1% error budget)
5. What's burn rate? (How fast error budget is being consumed: actual / allowed rate)

---

**Read `step-02.md`**
