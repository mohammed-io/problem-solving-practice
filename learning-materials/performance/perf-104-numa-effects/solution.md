# Solution: NUMA Effects

---

## Root Cause

Go scheduler is NUMA-unaware. Goroutines migrated between sockets, causing remote memory access.

---

## Solution

**NUMA-aware deployment:**

```yaml
# Run multiple processes, one per NUMA node
apiVersion: v1
kind: Deployment
metadata:
  name: app-numa-0
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: app
        resources:
          limits:
            cpu: "16"  # 16 cores = one socket
            memory: "64Gi"
---
apiVersion: v1
kind: Deployment
metadata:
  name: app-numa-1
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: app
        resources:
          limits:
            cpu: "16"  # Other socket
            memory: "64Gi"
```

**Tools:**
```bash
# Monitor NUMA effects
numastat -m
perf stat -e numa:mmem_local,numa:mmem_remote ./app
```

---

**Next Problem:** `network/net-101-dns-ttl/`
