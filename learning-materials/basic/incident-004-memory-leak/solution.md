# Solution: Memory Leak - Closures and Caching

---

## Root Cause

**Creating closures in a hot path that retain references to large objects.**

### The Bug

```javascript
async function checkFraud(payment) {
  const riskyUsers = await redis.get('risky_users');

  if (!riskyUsers) {
    // PROBLEM: This code path creates a NEW Set and Array every time
    const users = await db.query('SELECT user_id FROM risky_users WHERE active = true');

    // Convert rows to Set
    const riskySet = new Set(users.rows.map(r => r.user_id));

    await redis.setex('risky_users', 300, JSON.stringify([...riskySet]));

    return riskySet.has(payment.userId);
  }

  // PROBLEM: This creates a NEW Set from array on EVERY request
  const riskySet = new Set(JSON.parse(riskyUsers));  // ← LEAK!
  return riskySet.has(payment.userId);
}
```

### Why This Leaks

1. `users.rows` contains **all row objects** from the database (could be thousands)
2. `new Set(users.rows.map(r => r.user_id))` creates a Set, but the closure still references `users.rows`
3. The `Set` is created, but the **original `users.rows` array is never released**
4. On cache hit: `JSON.parse(riskyUsers)` creates an array, then `new Set(...)` creates a Set from it
5. **Neither is released** because they're captured in a closure that's never cleaned up

### Why GC Doesn't Help

JavaScript's garbage collector can only collect objects that are **no longer referenced**.

Here, the database result (`users.rows`) and the parsed JSON are:
1. Created in the hot path (every request)
2. Used briefly to create a Set
3. **But the original arrays stay in memory** because Node.js holds onto them

At 100 req/s, that's:
- 100 arrays per second
- Each array: ~1MB (for 1000 risky users)
- **100MB per second leaked**
- Hits 1GB limit in ~10 seconds

---

## The Fix

### Fix 1: Don't Create Intermediate Arrays

```javascript
async function checkFraud(payment) {
  const riskyUsers = await redis.get('risky_users');

  if (!riskyUsers) {
    // Fetch and cache
    const users = await db.query(
      'SELECT user_id FROM risky_users WHERE active = true'
    );

    // Convert directly to array of IDs (no Set)
    const userIds = users.rows.map(r => r.user_id);
    await redis.setex('risky_users', 300, JSON.stringify(userIds));

    return userIds.includes(payment.userId);
  }

  // Parse and check - NO Set creation
  const userIds = JSON.parse(riskyUsers);
  return userIds.includes(payment.userId);
}
```

### Fix 2: Bloom Filter (Better for Large Sets)

```javascript
const { BloomFilter } = require('bloom-filters');

// Create bloom filter ONCE at startup
let riskyBloomFilter = new BloomFilter(100000, 0.01); // 100k items, 1% false positive

// Refresh periodically
async function refreshRiskyUsers() {
  const users = await db.query(
    'SELECT user_id FROM risky_users WHERE active = true'
  );

  const newFilter = new BloomFilter(100000, 0.01);
  for (const row of users.rows) {
    newFilter.add(row.user_id);
  }

  riskyBloomFilter = newFilter; // Atomic swap
}

// Check is O(1) and minimal memory
function checkFraud(payment) {
  return riskyBloomFilter.has(payment.userId);
}
```

### Fix 3: Redis Set (Best for This Use Case)

```javascript
async function checkFraud(payment) {
  // Use Redis's native SISMEMBER - O(1) on server side
  const isRisky = await redis.sismember('risky_users_set', payment.userId);
  return isRisky === 1;
}
```

---

## Trade-offs

| Approach | Memory | CPU | Complexity | Best For |
|----------|--------|-----|------------|----------|
| **Array + includes** | High (linear search) | Low | Low | Small sets (<100 items) |
| **Set** | Medium | Medium | Low | Medium sets, JS-side |
| **Bloom Filter** | Very low | Low | Medium | Very large sets, false positive OK |
| **Redis Set** | None (on Redis) | Low | Low | Any size, network latency OK |

For payment fraud: **Redis Set** is ideal - moves memory burden to Redis, atomic operations.

---

## Systemic Prevention (Staff Level)

### 1. Memory Profiling in CI/CD

```bash
# Run load test with memory profiling
node --inspect payment-service.js &
PID=$!

# Load test
autocannon -c 100 -d 30 http://localhost:3000/api/payment

# Check memory
kill -USR1 $PID  # Trigger heap snapshot

# If memory grew >50MB during 30s test, fail deploy
```

### 2. Pre-Production Monitoring

```javascript
// Track heap usage
setInterval(() => {
  const used = process.memoryUsage().heapUsed / 1024 / 1024;
  const total = process.memoryUsage().heapTotal / 1024 / 1024;

  if (used > 500) {
    console.error(`High heap usage: ${used}MB / ${total}MB`);
    // Alert to monitoring
  }
}, 10000);
```

### 3. Code Review Guidelines

```markdown
## Memory Review Checklist

- [ ] No closures capturing large objects in hot paths
- [ ] Arrays/Sets are bounded (no unbounded growth)
- [ ] Database queries limit result set size (LIMIT, cursor)
- [ ] Cache hit paths don't create temporary large objects
- [ ] Streams used for large data processing
```

---

## Real Incident

**Uber (2016)**: Memory leak in payment processing service caused pods to be OOMKilled every few minutes during peak hours. Root cause: closures capturing large database result sets that were never garbage collected.

---

## Jargon

| Term | Definition |
|------|------------|
| **OOMKilled** | Container terminated for exceeding memory limit (Kubernetes OOMKiller) |
| **Memory leak** | Memory allocated but never released, causing continuous growth |
| **Heap** | Memory region where dynamic allocation happens (vs stack) |
| **Garbage collection (GC)** | Automatic memory reclamation for unused objects |
| **GC pressure** | How frequently GC needs to run (high pressure = performance issue) |
| **Closure** | Function that retains access to variables from its outer scope |
| **Event loop** | Node.js mechanism handling async operations (single-threaded) |
| **Bloom filter** | Probabilistic data structure for set membership (tiny memory, some false positives) |
| **Atomic swap** | Changing reference to new value without locks (thread-safe) |

---

## What As a Staff Engineer

You should have:

1. **Recognized the risk** in "parse JSON → new Set" on every request
2. **Asked "what happens when this set has 100,000 items?"**
3. **Suggested Redis Set** which moves complexity to Redis (battle-tested)
4. **Added memory profiling** to the CI/CD pipeline

The systemic issue: No one tested with production data volumes during staging.

---

**Next Problem:** `basic/design-001-user-schema/`
