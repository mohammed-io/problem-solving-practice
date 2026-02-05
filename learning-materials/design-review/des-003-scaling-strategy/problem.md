---
name: des-003-scaling-strategy
description: System design problem
difficulty: Advanced
category: Design Review / Scaling / Principal Engineer
level: Principal Engineer
---
# Design Review 003: Scaling Strategy Review

---

## The Design Document

```
# Scaling Strategy

Current: 1 server, 1000 QPS
Target: 10,000 QPS

Approach:
1. Add load balancer
2. Deploy 5 app servers (stateless)
3. Use Redis for session storage
4. Database: Read replicas for queries
5. Write: Primary only

Cache Strategy:
- Redis cache for hot data
- 1 hour TTL
- No cache invalidation planned

Deployment:
- Blue-green deployment
- One deployment per week
- No canary

Monitoring:
- Cloudwatch dashboards
- Manual alert review
```

---

## Your Review

As Principal Engineer, identify scaling risks.

---

## Concerns

1. **Database writes**: Single primary = bottleneck

2. **Cache stampede**: No invalidation + 1h TTL = stale data

3. **Deployment**: Weekly changes = slow iteration

4. **Cache unavailability**: What if Redis down?

5. **No canary**: All traffic switches at once

6. **Scaling reads only**: Write throughput unchanged

---

**Read `step-01.md`
