# Step 2: Understand the SLO Design

---

## Root Cause

**Capacity planning didn't account for N-1 failures:**

The system was designed to handle 1000 rps with 3 instances. But:
- Each instance was already at 30% CPU = 70% headroom
- When api-1 failed, remaining 2 instances needed to absorb 333 rps each
- But at higher load, **latency increases** (queueing theory)
- Higher latency = more concurrent requests = more memory = more GC = slower!

It's a **cascade failure**:

```
api-1 down
  → api-2, api-3 take more traffic
  → Latency increases (database queries slower under load)
  → More requests in-flight
  → Memory usage up
  → GC pauses increase
  → Requests timeout
  → 503 errors
  → SLO breach
```

---

## The Real Problem

**The SLO was designed for "normal" operations, not "degraded" operations:**

- SLO: 99.9% availability
- Design assumption: All 3 instances healthy
- Failure mode: What happens when 1 instance fails?

This is a **common mistake**: Setting SLOs without designing for failure modes.

---

## The Fix Strategy

**Immediate:** Add more capacity (manually scale up)

**Short-term:** Configure autoscaling with N+1 buffer

**Long-term:** Design SLOs around "minimum viable capacity"

---

## Questions

1. **Should the SLO be 99.9% if we can't handle instance failures?**

2. **What's the relationship between SLO, error budget, and engineering velocity?**

3. **How do you calculate "correct" SLOs?**

---

## Quick Check

Before moving on, make sure you understand:

1. What's the root cause of the SLO breach? (System designed for normal operation, not N-1 failure)
2. What's cascade failure? (One component fails → others overloaded → more failures)
3. What's the immediate fix? (Add more capacity manually)
4. What's the short-term fix? (Configure autoscaling with N+1 buffer)
5. What's the long-term fix? (Design SLOs around minimum viable capacity)

---

**When you've considered these, read `solution.md`**
