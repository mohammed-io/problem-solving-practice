# Solution: Connection Pool Exhaustion

---

## Root Cause

**Dual connection pools in the same process** - the new background job created its own pool instead of sharing the existing one.

### What Happened

1. Before deploy: 20 pods × 4 workers × 10 connections = 800 **possible** connections, but actual usage was ~250 under normal load

2. After deploy: Background job added its own pool (10 more per pod)
   - Possible connections: 20 pods × (4 workers × 10 + background 10) = **1000**
   - Under load, both pools compete for limited connections
   - Some workers get starved → timeout errors

3. The `pool.end()` in the background job wasn't in a try/finally, so on errors, connections weren't closed

---

## The Fix

### Immediate Fix (Rollback)

```bash
kubectl rollout undo deployment/payment-service
```

This removes the background job entirely, restoring normal operation.

### Code Fix (Share the Pool)

```javascript
// Create ONE pool per pod, at startup
const pool = new Pool({
  host: process.env.DB_HOST,
  max: 10,
  idleTimeoutMillis: 30000  // Close idle connections after 30s
});

// Use for requests
app.post('/api/payment', async (req, res) => {
  const client = await pool.connect();
  try {
    // ... process payment ...
  } finally {
    client.release();  // Always release back to pool
  }
});

// Use for background job too!
setInterval(async () => {
  const client = await pool.connect();
  try {
    const payments = await client.query('SELECT * FROM payments WHERE synced = false');
    // ... sync to warehouse ...
  } finally {
    client.release();  // Always release
  }
}, 30000);
```

### Configuration Fix

Reduce the pool size to mathematically fit:

```
Max connections per pod = floor(DB_max_connections / (pods × workers))

For 500 DB connections, 20 pods, 4 workers:
Max per pool = floor(500 / (20 × 4)) = floor(500 / 80) = 6
```

Set pool size to **6** instead of **10**.

---

## The Real Issue (Staff Level)

This incident reveals **systemic problems**:

### 1. No Connection Pool Monitoring

You should alert on:
- Connection pool utilization > 80%
- Connection wait time > 100ms
- Connection failures due to exhaustion

### 2. No Capacity Planning

Before deploying, someone should have calculated:
```
Do we have enough DB capacity for this new workload?
```

The math: 500 DB max connections / 20 pods / 4 workers = 6.25 max pool size

Current config of 10 was **already over-provisioned** before the background job!

### 3. Code Review Gap

The PR that added the background job should have been questioned:
- "Why a separate pool?"
- "Did we calculate DB capacity?"
- "What happens under load?"

### 4. Deployment Risk

Deploying to all 20 pods simultaneously meant:
- All pods immediately had the double-pool problem
- No gradual rollout to catch issues

---

## Prevention (Staff Level)

### 1. Connection Pool Dashboard

```
┌─────────────────────────────────────────────────────────┐
│  Connection Pool Health                                 │
├─────────────────────────────────────────────────────────┤
│  Total Allocated: 417 / 500 (83%)                      │
│  Active Connections: 312                                │
│  Idle Connections: 105                                  │
│  Waiting Clients: 23 ⚠️                                │
│                                                          │
│  By Pod:                                                 │
│  Pod 1:  18/20  ████████████████░                       │
│  Pod 2:  19/20  ██████████████████                      │
│  Pod 3:  16/20  ███████████████░░                       │
│  ...                                                    │
└─────────────────────────────────────────────────────────┘
```

### 2. Pre-Deploy Checklist

```markdown
## Database Impact Assessment

- [ ] Calculate connection requirements (pods × workers × pool_size)
- [ ] Verify against DB max_connections
- [ ] Add connection to existing pool (not new pool)
- [ ] Test at 2x expected load
- [ ] Add pool metrics to dashboard
```

### 3. Architecture Decision Record (ADR)

For future background jobs:

```markdown
# ADR: Background Jobs and Connection Pools

## Status
Accepted

## Context
Background jobs need database access but shouldn't create separate pools.

## Decision
All background jobs MUST:
1. Share the application's existing connection pool
2. Use shorter timeouts (don't hold connections during long processing)
3. Release connections in finally{} blocks
```

---

## Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| **Share pool** | Efficient use of connections | Background job can starve requests |
| **Separate pool** | Isolation between workloads | Requires more DB connections |
| **Sidecar pattern** | Complete isolation, can scale independently | More complex, more pods |
| **Queue-based** | Decouples processing from DB access | Adds queue infrastructure |

For payment processing, **share pool** is acceptable, but add **pool priorities** so requests get connections before background sync.

---

## Real Incident

**GitHub (2012)**: During a deploy, connection pool exhaustion caused site-wide outage. The issue: a new feature created additional connections without accounting for pool limits.

---

## Jargon

| Term | Definition |
|------|------------|
| **Connection pool** | Cache of reusable database connections maintained by application |
| **Lazy initialization** | Creating resources (connections) only when first needed, not upfront |
| **Connection starvation** | Requests waiting indefinitely for available connections |
| **Leak** | Resource allocated but never properly released (memory, connections, file descriptors) |
| **try/finally** | Code pattern ensuring cleanup runs even if errors occur |
| **Idle timeout** | Time after which unused resources are closed automatically |

---

## What As a Staff Engineer

You should have asked:

1. **"Has anyone calculated if we have enough DB capacity?"**
2. **"What's our rollback plan if this exceeds capacity?"**
3. **"Why aren't we monitoring connection pool utilization?"**

The systemic fix: Make connection pool math part of the architecture review process, not an afterthought.

---

**Next Problem:** `basic/incident-003-cache-stampede/`
