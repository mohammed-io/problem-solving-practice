# Step 1: Understanding CPU Throttling

---

## How CFS Throttling Works

```
CPU quota: 2000m (2 cores)
CPU period: 100ms

Every 100ms:
- Container gets 200ms of CPU time
- After 200ms used, container is throttled
- Throttled until next period

Problem:
- Container uses 200ms in first 20ms (spike)
- Throttled for remaining 80ms
- Result: Latency spike for requests during throttle
```

---

## Why 80% Shows Throttling

```
You see: 1600m / 2000m = 80%
Reality: Bursts above 2000m for short periods

Example:
- 95% of time: 500m usage
- 5% of time: 4000m usage (spike to 4 cores)
- Average: 1600m
- BUT: Spikes cause throttling!

kubectl top pod shows AVERAGE
cat /sys/fs/cgroup/cpu/cpu.stat shows THROTTLES
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's CFS CPU throttling? (Linux Completely Fair Scheduler limits container CPU usage per period)
2. What's CPU quota? (Amount of CPU time allocated per period, e.g., 2000m = 2 cores worth)
3. What's the CPU period? (Time window for quota, default 100ms in Kubernetes)
4. Why does throttling cause latency spikes? (Container can't run until next period, requests queue)
5. Why can average usage be misleading? (Spikes above quota cause throttling even if average is low)

---

**Read `step-02.md`
