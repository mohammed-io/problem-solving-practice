# Step 1: Scaling Issues

---

## Problems

**1. Write Bottleneck**
```
10,000 QPS with 20% writes = 2,000 write QPS
Single database primary can handle ~1,000 write QPS (typical)
Result: Primary becomes bottleneck

Need: Sharding, write forwarding, or CQRS
```

**2. Cache Stampede Risk**
```
1 hour TTL + no invalidation:
- Data can be stale for 1 hour
- Multiple cache misses → thundering herd on DB
- No way to force refresh

Need: Shorter TTL, active invalidation, cache warming
```

**3. Deployment Risk**
```
Weekly deployments:
- 2-week lead time for fixes
- High risk per deployment
- No gradual rollout

Need: Canary deployment, feature flags
```

---

**Read `solution.md`
