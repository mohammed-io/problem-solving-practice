# Solution: SLI Breach - Inadequate Capacity Planning for N-1

---

## Root Cause

**System designed for normal capacity, not degraded (N-1) capacity:**

```
Normal: 3 instances × 333 rps = 1000 rps @ 30% CPU
Failed: 2 instances × 500 rps = 1000 rps @ 95% CPU (503s!)

The system couldn't handle losing one instance while maintaining traffic.
```

The SLO (99.9% availability) assumed all instances healthy. When one instance failed, the remaining instances couldn't handle the load, causing cascade failure.

---

## The Immediate Fix

### Fix 1: Manual Scale-Up

```bash
# Add 2 more instances immediately
kubectl scale deployment api --replicas=5

# Now 5 instances share 1000 rps
# Each instance: 200 rps @ ~18% CPU
```

### Fix 2: Traffic Throttling

```yaml
# Rate limit to protect remaining instances
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  annotations:
    nginx.ingress.kubernetes.io/limit-rps: "800"  # Under new capacity
spec:
  rules:
  - host: api.example.com
    http:
      paths:
      - backend:
          service:
            name: api
            port:
              number: 8080
```

Return 429 (Too Many Requests) instead of 503 (Service Unavailable). 429s don't count against SLO if configured correctly!

---

## Long-term Solutions

### Solution 1: Autoscaling with N+1 Buffer

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 4        # N+1 buffer (can lose 1 and still be fine)
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 50  # Trigger scale at 50%, not 80%
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30    # Quick scale up
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
    scaleDown:
      stabilizationWindowSeconds: 300   # Slow scale down (avoid flapping)
```

**Key insight:** Scale up at 50% CPU so losing an instance doesn't push others into danger zone.

### Solution 2: Redundancy Across Zones

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  replicas: 9
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 3
      maxUnavailable: 0  # Never allow replicas < desired
  topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: DoNotSchedule
    labelSelector:
      matchLabels:
        app: api
```

**Result:**
- 3 zones × 3 instances = 9 instances total
- Can lose an entire zone and still have 6 instances
- Each zone handles ~333 rps, well within capacity

### Solution 3: SLO-Based Error Budget Policy

**Define burn rate alerts:**

```promql
# Alert if burning error budget 2x faster than allowed
- alert: ErrorBudgetBurn
  expr: |
    (
      (1 - slo:availability:ratio30d) * 30 * 24 * 3600
      - (1 - slo:availability:ratio30d_offset_1d) * 30 * 24 * 3600
    ) / 86400 > (0.001 / 30) * 2
  labels:
    severity: warning
  annotations:
    summary: "Error budget burning at 2x rate"

# Alert if burned through budget entirely
- alert: ErrorBudgetExhausted
  expr: |
    (1 - slo:availability:ratio30d) * 30 * 24 * 3600 > 2592
  labels:
    severity: critical
  annotations:
    summary: "Error budget exhausted - STOP FEATURES"
```

**Error Budget Policy:**

| Burn Rate | Action |
|-----------|--------|
| 1x (normal) | Business as usual |
| 2x | Add monitoring, investigate |
| 10x | Page on-call, stop releases |
| 50x+ | STOP ALL WORK, fix reliability |

---

## Systemic Prevention (Staff Level)

### 1. Define SLIs Correctly

**Bad SLI:** "Uptime of instances" (doesn't measure user experience)

**Good SLIs:**
```promql
# Availability: Successful requests / Total requests
sum(rate(http_requests_total{status!~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))

# Latency: 95th percentile < 100ms
histogram_quantile(0.95,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
)

# Freshness: Data age < 5 minutes
max by (shard) (time() - last_successful_update_seconds)
```

### 2. Set SLOs Based on User Needs

**Question:** What do users actually need?

- **Critical payment API:** 99.99% (5 minutes downtime/year)
- **Internal admin API:** 99% (7 hours downtime/month)
- **Analytics dashboard:** 95% (1.5 days downtime/month)

**Not all services need 99.9%!**

### 3. Test Failure Modes

```bash
# Chaos engineering: Test N-1 scenarios
kubectl chaos disconnect network

# Test instance failure
kubectl delete pod api-1

# Test zone failure
kubectl cordon us-east-1a

# Monitor: Does SLO hold?
```

### 4. SLO Review Cadence

**Quarterly SLO Review:**
1. Are we meeting SLOs?
2. Are SLOs too tight/loose?
3. What's our burn rate trend?
4. What incidents caused breaches?
5. Can we improve architecture?

---

## Real Incident Reference

**Google SRE Book (2016):** Introduces error budget concept. Teams stop feature development when error budget is burned. Reliability work prioritized over features when budget depleted.

**Dropbox (2018):** SLO breach during single AZ failure. Had configured autoscaling based on aggregate CPU, not per-zone capacity. Fixed by adding zone-aware autoscaling.

---

## Jargon

| Term | Definition |
|------|------------|
| **SLI (Service Level Indicator)** | Metric measuring service performance (latency, error rate, availability) |
| **SLO (Service Level Objective)** | Target value for SLI; e.g., "99.9% of requests succeed" |
| **SLA (Service Level Agreement)** | Contract with customers specifying SLOs and penalties |
| **Error budget** | Amount of failure allowed; 99.9% = 0.1% budget; when burned, stop features |
| **Burn rate** | How fast error budget consumed; "10x burn rate" = 10x faster than allowed |
| **N-1 resilience** | System works when losing 1 component (N-1 remaining) |
| **Cascade failure** | When one component's failure causes others to fail (domino effect) |
| **Autoscaling** | Automatically adding/removing instances based on load |
| **Topological spread** | Distributing pods across failure domains (zones, nodes) |

---

## Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| **N+1 buffer** | Handles instance failures gracefully | Higher infrastructure cost |
| **Zone redundancy** | Survives entire zone loss | Complex routing, higher latency |
| **Aggressive autoscaling** | Cost-effective for variable load | Lag time in scaling (minutes) |
| **Lower SLO (99%)** | Cheaper, achievable | May not meet customer expectations |
| **Rate limiting** | Protects system, predictable | Drops requests (429s) |

For most APIs: **N+1 buffer + zone redundancy + aggressive autoscaling** is recommended.

---

**Next Problem:** `intermediate/incident-015-cache-avalanche/`
