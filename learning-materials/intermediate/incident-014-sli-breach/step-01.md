# Step 1: Analyze the Capacity

---

## Hint

Before the incident:
- 3 instances, each handling ~333 rps (1000 rps total)
- Each instance at ~30% CPU

After api-1 went down:
- 2 instances handling 1000 rps
- Each instance now handling ~500 rps

**What happened to CPU utilization?**

```
Before: 333 rps → 30% CPU
After:  500 rps → ?% CPU
```

---

## The Calculation

Assuming linear scaling (simplified):

```
CPU = (requests per second / capacity) × 100%

Before:
333 rps / capacity_per_instance = 0.30
capacity_per_instance ≈ 1111 rps

After (api-1 down):
500 rps / 1111 rps ≈ 45% CPU

But wait! The logs show api-3 at 95% CPU, not 45%!
```

**What could cause non-linear scaling?**

---

## Think About This

1. **Connection pooling:** When traffic doubles, do connections double?
2. **Database queries:** More requests = more DB queries = slower queries
3. **Memory pressure:** More concurrent requests = more memory used
4. **Garbage collection:** Go/Java/Python GC pauses more frequent under load

---

## Quick Check

Before moving on, make sure you understand:

1. What happened when api-1 went down? (2 instances handled 1000 rps instead of 3)
2. Why was CPU 95% instead of 45%? (Non-linear scaling - more load = higher latency = more contention)
3. What's cascade failure? (One failure causes others, like latency → memory → GC → timeout)
4. What's queueing theory? (Study of waiting lines; higher load = exponentially longer wait times)
5. Why is N-1 capacity planning important? (Systems must handle failures without SLO breach)

---

**When you have a theory, read `step-02.md`**
