# Step 2: Scaling Strategy

---

## Solutions

### 1. Write Scaling

**Option A: Database Sharding**
```
Shard by user_id:
- User 1-10000 → DB primary 1
- User 10001-20000 → DB primary 2
- Each user's data on one shard
- Cross-shard queries limited

Pros: Linear write scaling
Cons: Complex queries, re-sharding
```

**Option B: CQRS**
```
Write side: PostgreSQL (single primary)
Read side: Multiple read replicas + denormalized views

Pros: Reads scale, writes consistent
Cons: Eventual consistency on reads
```

**Option C: Write Forwarding**
```
App servers forward writes to write service
Write service batches writes
Reduces connection overhead

Pros: Simple, reduces load
Cons: Single bottleneck still exists
```

---

### 2. Cache Improvements

```python
# Cache stampede prevention with locks
async def get_user(user_id):
    key = f"user:{user_id}"

    # Try cache
    user = await redis.get(key)
    if user:
        return user

    # Acquire lock
    lock_key = f"lock:{key}"
    lock = await redis.set(lock_key, "1", NX, EX=10)

    if lock:
        try:
            # Fetch from DB (only we do this!)
            user = await db.query("SELECT * FROM users WHERE id = $1", user_id)
            await redis.setex(key, 300, json.dumps(user))
            return user
        finally:
            await redis.del(lock_key)
    else:
        # Wait for lock holder, then retry cache
        await asyncio.sleep(0.1)
        return await get_user(user_id)  # Retry
```

---

### 3. Deployment Strategy

```
Canary Deployment:
1. Deploy to 1 server (5% of traffic)
2. Monitor metrics (error rate, latency)
3. If healthy, expand to 10%, 25%, 50%, 100%
4. If unhealthy, rollback immediately

Feature Flags:
- Feature enabled for 1% of users
- Gradually increase
- Instant rollback without deploy
```

---

## Architecture Diagram

```
                    ┌─────────────────────────────────────┐
                    │         Load Balancer               │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
         ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
         │ App Svc │         │ App Svc │         │ App Svc │
         │ Node A  │         │ Node B  │         │ Node C  │
         └────┬────┘         └────┬────┘         └────┬────┘
              │                    │                    │
              └────────────────────┼────────────────────┘
                                   │
                    ┌──────────────┴───────────┐
                    │                         │
              ┌─────▼─────┐            ┌──────▼──────┐
              │ Redis     │            │ PostgreSQL  │
              │ Cluster   │◄───────────►│ + Replicas  │
              └───────────┘            └─────────────┘
                   │                         │
                   │     ┌─────────────────┘
                   │     │
              ┌────▼────▼────┐
              │  Cache       │
              │  Warming     │
              │  Service     │
              └──────────────┘
```

---

## Scaling Targets

| Metric | Current | Target | Strategy |
|--------|---------|--------|----------|
| Read QPS | 8,000 | 50,000 | Add replicas, cache |
| Write QPS | 2,000 | 10,000 | CQRS or sharding |
| Cache hit rate | 80% | 95% | Cache warming |
| P95 latency | 200ms | 50ms | Index optimization |
| Deploy frequency | Weekly | Daily | Canary + feature flags |

---

## Implementation Priority

**Week 1:**
1. Add cache warming service
2. Implement cache stampede prevention
3. Set up read replicas

**Week 2:**
1. Implement CQRS pattern
2. Set up canary deployment
3. Add feature flag system

**Week 3:**
1. Database sharding (if needed)
2. Performance testing
3. Documentation

---

**Now read `solution.md` for complete reference.**
