# Solution: CPU Throttling

---

## Root Cause

CPU bursts caused throttling even though average usage was low.

---

## Solution

**Set appropriate limits + monitor throttling:**

```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: app
    resources:
      requests:
        cpu: 1000m      # Guaranteed baseline
      limits:
        cpu: 8000m      # Allow 4x burst
        # Or omit limits for unlimited
```

**Monitor throttling:**
```bash
# Check throttling
kubectl exec pod -- cat /sys/fs/cgroup/cpu/cpu.stat
# Look for: nr_throttled and throttled_time

# Prometheus query
rate(container_cpu_cfs_throttled_periods_total[5m]) > 0.1
```

---

**Next Problem:** `performance/perf-104-numa-effects/`
