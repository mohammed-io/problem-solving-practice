# Solution: Cache Avalanche - Synchronized Cache Expiration

---

## Root Cause

**Cache warming with fixed TTL** caused synchronized expiration:

```
100 servers start at 09:00
→ Each loads 100,000 users with TTL = 1 hour
→ At 10:00 ± 10 seconds: 10,000,000 entries expire
→ 50,000 req/s hit database (capacity: 5,000)
→ Complete overload
```

The problem wasn't cache warming itself—it was the **synchronized TTL**.

---

## Immediate Fixes

### Fix 1: Kill the Deployment

```bash
# Rollback to previous version
kubectl rollout undo deployment/api

# Or manually scale down new deployment
kubectl scale deployment/api-v2 --replicas=0
kubectl scale deployment/api-v1 --replicas=100
```

### Fix 2: Add Jitter TTL

```go
import (
    "math/rand"
    "time"
)

func cacheWithJitter(key string, value interface{}, baseTTL time.Duration) {
    // Add ±10% jitter to spread out expirations
    jitterRange := int64(baseTTL) / 10
    jitter := time.Duration(rand.Int63n(jitterRange*2) - jitterRange)

    finalTTL := baseTTL + jitter

    cache.Set(key, value, finalTTL)
}
```

**Result:** Expirations spread over ±6 minutes instead of ±10 seconds.

---

## Long-term Solutions

### Solution 1: Probabilistic Cache Expiration

```go
// "Netflix Chaos Monkey" approach for cache
func cacheWithProbabilisticExpiry(key string, value interface{}, ttl time.Duration) {
    // 5% of entries expire 20% early
    // 5% of entries expire 40% early
    // This smooths the expiration curve
    roll := rand.Float64()

    switch {
    case roll < 0.05:
        ttl = ttl * 3 / 5  // 40% early
    case roll < 0.10:
        ttl = ttl * 4 / 5  // 20% early
    }

    cache.Set(key, value, ttl)
}
```

**Expiration distribution:**
```
Normal:  |████████████████████| (all at once)
Jitter:  |███░███░███░███░███░| (spread out)
Probabilistic: |█████████░░░░░████| (smooth curve)
```

### Solution 2: Leased Caching (Redis)

Redis supports **key expiration with lease renewal**:

```go
// Instead of fixed TTL, use a lease
func getWithLease(key string) (interface{}, error) {
    // Try cache
    val, err := redis.Get(key)

    if err == redis.Nil {
        // Cache miss - fetch from DB
        val = fetchFromDB(key)

        // Set with TTL
        redis.SetEx(key, val, 1*time.Hour)
    }

    return val, nil
}

// Background job "refreshes" hot keys before they expire
func refreshHotKeys() {
    for {
        hotKeys := getHotKeys()  // Keys accessed > 100 times/minute

        for _, key := range hotKeys {
            ttl := redis.TTL(key)
            if ttl < 10*time.Minute {
                // Refresh before expiration
                val := fetchFromDB(key)
                redis.SetEx(key, val, 1*time.Hour)
            }
        }

        time.Sleep(1 * time.Minute)
    }
}
```

**Result:** Hot keys never expire naturally; they're refreshed proactively.

### Solution 3: Cache Warming Done Right

```go
// Warm cache gradually, not all at once
func WarmupCacheGradual(db *sql.DB, cache *memcached.Client) {
    const batchSize = 1000
    const delayBetweenBatches = 100 * time.Millisecond

    offset := 0
    for {
        // Fetch batch
        rows, _ := db.Query(`
            SELECT id FROM users
            WHERE followers_count > 10000
            ORDER BY last_active DESC
            LIMIT $1 OFFSET $2
        `, batchSize, offset)

        var users []User
        for rows.Next() {
            var user User
            rows.Scan(&user.ID, &user.Username, /* ... */)
            users = append(users, user)
        }

        if len(users) == 0 {
            break
        }

        // Cache this batch
        for _, user := range users {
            key := fmt.Sprintf("user:%d", user.ID)
            cacheWithJitter(key, user, 1*time.Hour)
        }

        offset += batchSize

        // CRITICAL: Delay between batches
        time.Sleep(delayBetweenBatches)
    }
}

// ALSO: Stagger server startups
func main() {
    // Add random delay before warming
    delay := time.Duration(rand.Intn(60)) * time.Second
    log.Printf("Waiting %v before cache warmup", delay)
    time.Sleep(delay)

    WarmupCacheGradual(db, cache)
    startAPI()
}
```

**Result:** Each server warms cache over ~17 minutes (100 batches × 100ms), with random initial delays.

### Solution 4: Request Coalescing

```go
// singleflight package ensures only one request per key
import "golang.org/x/sync/singleflight"

var sf singleflight.Group

func GetUserProfile(ctx context.Context, userID int64) (*Profile, error) {
    key := fmt.Sprintf("user:%d", userID)

    // Try cache first
    if cached, found := cache.Get(key); found {
        return cached.(*Profile), nil
    }

    // Use singleflight to coalesce concurrent requests
    result, err, shared := sf.Do(key, func() (interface{}, error) {
        // Only ONE goroutine executes this, even if 1000 concurrent requests
        profile, err := db.QueryRow("SELECT * FROM users WHERE id = $1", userID)
        if err != nil {
            return nil, err
        }

        // Populate cache
        cache.Set(key, profile, 1*time.Hour)

        return profile, nil
    })

    if err != nil {
        return nil, err
    }

    if shared {
        metrics.CoalescedRequests.Inc()  // Monitor coalescing rate
    }

    return result.(*Profile), nil
}
```

**Result:** If 1000 requests simultaneously miss cache for same user, only 1 DB query happens.

---

## Systemic Prevention (Staff Level)

### 1. Monitor Cache Expiration Distribution

```promql
# Cache expiration rate (should be smooth curve)
rate(cache_expirations_total[1m])

# Alert if spike detected
- alert: CacheExpirationSpike
  expr: |
    rate(cache_expirations_total[1m]) > 10000
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: "Cache expiring too fast - potential avalanche"
```

### 2. Cache Health Dashboard

Track these metrics:
- **Hit rate:** Should be >90%
- **Expiration rate:** Should be smooth, not spiky
- **Coalescing rate:** How many requests saved by singleflight
- **TTL distribution:** Histogram of cache entry ages

### 3. Load Testing with Cache Scenarios

```bash
# Test: Simulate cache expiration
./load-test \
  --cache-expiration-spread=0 \    # No spread (bad)
  --requests-per-second=50000 \
  --duration=10m

# Test: With jitter
./load-test \
  --cache-expiration-spread=600 \   # 10 minutes spread (good)
  --requests-per-second=50000 \
  --duration=10m
```

### 4. Runbook: Cache Avalanche Response

```markdown
## Cache Avalanche Incident Runbook

### Detection
- Cache hit rate drops suddenly (<50%)
- Database load spikes (>3x normal)
- API latency increases dramatically

### Immediate Actions
1. Enable request coalescing (if not already)
2. Rate limit incoming traffic (protect DB)
3. Consider disabling cache temporarily (let system stabilize)
4. Scale database horizontally if possible

### Recovery
1. Gradually re-enable caching with jitter
2. Monitor expiration curve for smoothness
3. Post-incident review: Why did cache synchronize?
```

---

## Real Incident

**Facebook (2012):** Memcached cache expiration caused database overload. Popular items cached with same TTL expired simultaneously during traffic spikes. Fixed with probabilistic expiration and leased caching.

**Instagram (2014):** Redis cache avalanche after deployment. All cache warmed with fixed TTL. Fixed by adding jitter and staggering warmups.

---

## Jargon

| Term | Definition |
|------|------------|
| **Cache avalanche** | Many cache entries expire simultaneously, overwhelming backend |
| **Cache stampede** | Single hot key expires, many requests hit backend for same data |
| **Jitter** | Random variation added to prevent synchronized behavior |
| **TTL (Time To Live)** | How long cached data remains valid |
| **Singleflight** | Coalescing concurrent identical requests into one |
| **Leased caching** | Proactively refresh hot keys before expiration |
| **Coalescing rate** | Number of duplicate requests avoided by singleflight |
| **Cache warming** | Pre-loading cache with expected data |

---

## Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| **Jitter TTL** | Simple, effective | Doesn't eliminate spikes, just spreads them |
| **Probabilistic expiration** | Smooth curve, predictable | More complex, some cache waste |
| **Leased caching** | Hot keys never expire | Extra background work, complex |
| **Request coalescing** | Prevents stampedes | Only helps for duplicate requests |
| **Gradual warmup** | Predictable load | Slower startup, more complex |
| **Disable cache temporarily** | Stabilizes system quickly | Increases DB load during incident |

For most systems: **Jitter TTL + Request Coalescing + Gradual Warmup** is best.

---

**Next Problem:** `intermediate/incident-016-slow-log/`
