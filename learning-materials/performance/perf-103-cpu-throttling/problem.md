---
name: perf-103-cpu-throttling
description: CPU Throttling
difficulty: Intermediate
category: Performance / CPU / Containers
level: Senior Engineer
---
# Performance 103: CPU Throttling

---

## The Situation

Your containerized service has CPU limit of 2 cores. Under load, latency degrades.

**Metrics:**
```
CPU limit: 2000m (2 cores)
Usage: Stays at 80% (1600m)

But: P99 latency increases from 10ms to 500ms under load
```

---

## The Problem

```
CPU throttling in Kubernetes:

Container asks for CPU → scheduler gives 1ms
Process uses 1ms → scheduler pauses (throttled)
Process waits → scheduler gives 1ms
Result: Spiky latency

kubectl top pod shows 80% CPU
But /sys/fs/cgroup/cpu/cpu.stat shows:
  nr_throttled: 1,234,567
  throttled_time: 12345678912 nanoseconds
```

---

## The Jargon

| Term | Definition |
|------|------------|
| **CPU Throttling** | Pausing process that exceeds CPU quota |
| **CFS** | Completely Fair Scheduler |
| **Quota** | CPU time allowed per period |
| **Period** | Time window for quota (100ms default) |
| **Request** | Guaranteed CPU |
| **Limit** | Maximum CPU |

---

## Questions

1. **Why does CPU throttle at 80% usage?**

2. **What's the difference between request and limit?**

3. **How do CPU bursts work?**

4. **What's the impact of CPU throttling on latency?**

5. **As a Senior Engineer, how do you set CPU limits?**

---

**Read `step-01.md`
