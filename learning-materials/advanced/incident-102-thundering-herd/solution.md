# Solution: Thundering Herd - Cache Restart Resilience

---

## Root Cause

**Simultaneous cache miss** after restart:
- Redis restarted → all cache empty
- 50,000 req/s → all miss cache
- Database overwhelmed (20x capacity)

---

## Solutions

### Solution 1: Singleflight (Request Coalescing)

```go
var sf singleflight.Group

func GetUserProfile(ctx context.Context, userID int64) (*Profile, error) {
    key := "user:" + strconv.FormatInt(userID, 10)

    // Try cache
    if cached, err := redis.Get(key); err == nil {
        return unserialize(cached), nil
    }

    // Coalesce identical requests
    result, err, shared := sf.Do(key, func() (interface{}, error) {
        profile, err := db.QueryRow("SELECT * FROM users WHERE id = $1", userID)
        if err != nil {
            return nil, err
        }
        redis.Set(key, serialize(profile), 1*time.Hour)
        return profile, nil
    })

    if shared {
        metrics.CoalescedRequests.Inc()  // Track how many saved
    }

    return result.(*Profile), err
}
```

**Impact:** 1000 concurrent requests for same user = 1 DB query.

### Solution 2: Background Refresh

```go
func GetUserProfile(userID int64) (*Profile, error) {
    key := "user:" + strconv.FormatInt(userID, 10)

    cached, err := redis.Get(key)
    if err != nil {
        // Cache miss: fetch synchronously
        return fetchAndCache(userID, key)
    }

    // Probabilistic refresh for hot keys
    if rand.Float64() < 0.05 {  // 5% of requests
        go fetchAndCache(userID, key)  // Background
    }

    return unserialize(cached), nil
}
```

**Impact:** Hot keys never expire naturally; spread refresh load.

### Solution 3: Gradual Cache Warming

```go
// After Redis restart, warm cache gradually
func WarmCacheGradually() {
    // Get popular keys from analytics
    popularKeys := getPopularKeys()  // Top 10000 users

    // Process in batches with delay
    for _, batch := range chunk(popularKeys, 100) {
        for _, userID := range batch {
            go fetchAndCache(userID, "user:"+strconv.FormatInt(userID, 10))
        }
        time.Sleep(100 * time.Millisecond)  // Delay between batches
    }
}
```

**Impact:** 10,000 keys warmed over ~10 seconds, not instantly.

### Solution 4: Cache Replica During Restart

```
┌─────────────────────────────────────────────────────────┐
│                    Application                          │
└────────┬────────────────────────────────────────────────┘
         │
         ├───► Primary Redis (restarting)
         │
         └───► Replica Redis (still warm) ──► Promote to primary
```

During restart:
1. Promote replica to primary
2. Restart old primary (now becomes replica)
3. No cache cold start

---

## Systemic Prevention

### Monitoring

```promql
# Cache hit rate
- alert: CacheHitRateLow
  expr: |
    rate(cache_hits_total[5m]) / rate(cache_requests_total[5m]) < 0.8
  for: 2m
  labels:
    severity: warning

# Singleflight coalescing rate
- alert: HighCoalescingRate
  expr: |
    rate(singleflight_coalesced_total[5m]) > 1000
  labels:
    severity: info  # Actually good, but track it

# Cache restart detected
- alert: CacheRestarted
  expr: |
    cache_keys_total < 1000
  for: 1m
  labels:
    severity: critical
```

### Runbook

```markdown
## Cache Restart Response

### Detection
- Cache keys < 1000 (normally millions)
- Hit rate drops to < 10%

### Immediate Actions
1. Verify singleflight enabled (should be always on)
2. Enable gradual warmup if not running
3. Consider rate limiting if overload continues

### Prevention
1. Use replica during restart
2. Keep singleflight always enabled
3. Monitor warmup progress
```

---

## Trade-offs

| Solution | Pros | Cons |
|----------|------|------|
| **Singleflight** | Prevents stampede, simple | Only helps duplicate requests |
| **Background refresh** | Hot keys never expire | Extra background load |
| **Gradual warmup** | Controlled load | Slower full availability |
| **Cache replica** | No cold start | Double infrastructure cost |

---

## Real Incident Reference

**Facebook (2011):** Memcached restart caused thundering herd. Fixed with singleflight and gradual warmup.

**Discord (2017):** Redis restart overwhelmed database. Fixed with request coalescing and probabilistic refresh.

---

**Next Problem:** `advanced/incident-103-phoenix-deadlock/`
