# Step 05: Understanding SLOs and SLIs

---

## The Problem

The team has **no defined service level objectives**.

```
Product Manager: "Is the system healthy?"
Engineer: "Umm... CPU is at 45%, so... yes?"
Product Manager: "But users are complaining about slow checkout."
Engineer: "Oh, let me check the logs..."

❌ No shared understanding of "healthy"
❌ Can't prioritize work
❌ Don't know if we're meeting user expectations
```

---

## Question: What is an SLO?

**SLO** = Service Level Objective (a target)
**SLI** = Service Level Indicator (a measurement)

Think of it like a car dashboard:

```
┌─────────────────────────────────────────┐
│  SLI: Speedometer                      │
│  "Current speed: 65 mph"               │
│                                         │
│  SLO: Speed limit                      │
│  "Target: ≤ 65 mph"                    │
│                                         │
│  If speed > 65, you get a ticket ❌    │
└─────────────────────────────────────────┘
```

---

## Common SLIs

| SLI | Example | Good SLO |
|-----|---------|----------|
| **Availability** | % of successful requests | 99.9% |
| **Latency** | 95th percentile response time | < 500ms |
| **Freshness** | Time for data to propagate | < 60s |
| **Correctness** | % of accurate results | > 99.9% |
| **Durability** | Probability data isn't lost | 99.999% |

---

## From User Requirements to SLOs

Start with what users care about:

```
User says: "I need the site to be fast."

❌ Bad SLO: "Average latency < 100ms"
   → Averages hide outliers. 50% of users could be slow.

❌ Bad SLO: "p99 latency < 100ms"
   → Too expensive. You're optimizing for the worst case.

✅ Good SLO: "p95 latency < 500ms"
   → 95% of users see fast response.
   → Achievable without extreme cost.

User says: "I need the site to be up."

❌ Bad SLO: "100% uptime"
   → Impossible. You can't prevent all failures.

✅ Good SLO: "99.9% uptime"
   → Allows ~43 minutes of downtime per month.
   → Achievable with good engineering.
```

---

## The Error Budget Concept

**Error budget** = How much "bad" is allowed.

```
SLO: 99.9% availability
Error budget: 0.1% (or 43 minutes/month)

┌─────────────────────────────────────────────────────────────┐
│                    Error Budget (100%)                      │
│  ┌──────────────────────────────────────────────┐          │
│  │████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░│          │
│  └──────────────────────────────────────────────┘          │
│   Spent: 60%                     Remaining: 40%               │
│                                                             │
│  If you spend your budget, you can't release risky features │
│  If budget is high, you can move faster                      │
└─────────────────────────────────────────────────────────────┘
```

**Key insight:** Error budget enables innovation. You're allowed to fail sometimes, as long as you stay within budget.

---

## Burn Rate

How fast are you burning through your error budget?

```
Normal error rate: 0.01% (for 99.99% SLO)
Current error rate: 0.1%

Burn rate = 0.1% / 0.01% = 10x

At 10x burn rate:
- You burn 1 month of budget in 3 days! 🔥
- Trigger P1 alert immediately
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's the difference between SLI and SLO? (Measurement vs target)
2. What is error budget? (How much failure is allowed)
3. What is burn rate? (How fast you're spending the budget)
4. Why is "100% uptime" a bad SLO? (Impossible, too expensive)

---

**Ready to implement SLO-based alerting? Read `step-06.md`**
