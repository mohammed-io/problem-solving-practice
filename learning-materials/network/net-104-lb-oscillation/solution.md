# Solution: Load Balancer Oscillation

---

## Root Cause

Health checks failed under load because they shared resources with traffic. LB created the problem it detected.

---

## Solution

**Lightweight health endpoint + hysteresis:**

```yaml
# Kubernetes probes
livenessProbe:
  httpGet:
    path: /healthz  # Just check if running
    port: 8081
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 2
  failureThreshold: 5  # Only restart after 5 failures

readinessProbe:
  httpGet:
    path: /ready  # Check dependencies
    port: 8081
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 2
  failureThreshold: 3  # Remove from LB after 3 failures
```

**Separate server for health:**
- Different port
- Different goroutine pool
- Simple response (no external calls)

---

**Status:** All network problems complete. Moving to design review problems.
