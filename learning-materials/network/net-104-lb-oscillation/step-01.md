# Step 1: Understanding Oscillation

---

## The Death Spiral

```
Healthy → More Traffic → Higher Load
   ↓                           ↓
Pass checks? ← Slower response ←
   │
   No (under load)
   ↓
Unhealthy → Less Traffic → Lower Load
   ↓                           ↓
Fail checks? ← Faster response ←
   │
   Yes (low load)
   ↓
Healthy → (cycle repeats)
```

---

## Why It Happens

```
Health check: GET /health
Normal: 10ms response
Under load: 500ms response (processing queue)

LB timeout: 100ms
Result: Under load, health check times out!
Pod marked unhealthy even though it's working
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's LB oscillation? (Pods repeatedly marked healthy/unhealthy due to load-sensitive health checks)
2. What's the death spiral pattern? (Healthy → more traffic → slower response → unhealthy → less traffic → repeat)
3. Why do health checks fail under load? (Processing queue makes /health respond slower, exceeding timeout)
4. What's the cycle of oscillation? (Under load → health check timeout → removed from LB → load drops → health check passes → re-added → repeat)
5. What's the root cause? (Health check depends on same resources handling application traffic)

---

**Read `step-02.md`
