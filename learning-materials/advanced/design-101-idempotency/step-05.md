# Step 05: Production Concerns

---

## Key Expiration Strategy

How long should idempotency keys persist?

```
Too short (5 minutes):
  Client retries after 5 minutes → Double charge ❌

Too long (30 days):
  Redis memory bloat ❌
  Stale data forever ❌

Optimal (24-48 hours):
  Covers retry window ✓
  Reasonable memory ✓
  Industry standard ✓
```

---

## Implementation: Tiered Expiration

```go
const (
    // Lock expires quickly (in case of crash)
    LockTTL = 30 * time.Second

    // Success data persists for retry window
    SuccessTTL = 48 * time.Hour

    // Failure data persists briefly (for quick retry)
    FailureTTL = 1 * time.Hour
)

func (c *AtomicCache) SetResponse(ctx context.Context, idempotencyKey string, response *CachedResponse) error {
    var ttl time.Duration

    // Different TTL based on status
    if response.StatusCode >= 400 && response.StatusCode < 500 {
        // Client errors: shorter TTL (allow fix and retry)
        ttl = FailureTTL
    } else if response.StatusCode >= 500 {
        // Server errors: very short TTL (service might be back)
        ttl = 5 * time.Minute
    } else {
        // Success: full TTL
        ttl = SuccessTTL
    }

    dataKey := DataPrefix + idempotencyKey
    data, _ := json.Marshal(response)
    return c.client.Set(ctx, dataKey, data, ttl).Err()
}
```

---

## Memory Management

```go
// Estimate memory usage
type CacheStats struct {
    TotalKeys    int64
    TotalMemory  int64
    AvgKeySize   int64
}

func (c *AtomicCache) GetStats(ctx context.Context) (*CacheStats, error) {
    // Use SCAN to count keys
    var count int64
    var size int64

    iter := c.client.Scan(ctx, 0, DataPrefix+"*", 0).Iterator()
    for iter.Next(ctx) {
        count++
        // Get size of this key
        key := iter.Val()
        memory := c.client.MemoryUsage(ctx, key).Val()
        size += memory
    }

    return &CacheStats{
        TotalKeys:   count,
        TotalMemory: size,
        AvgKeySize:  size / count,
    }, nil
}

// Set maxmemory policy in Redis:
// redis-cli CONFIG SET maxmemory 1gb
// redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

---

## Database Persistence (Audit Trail)

For compliance, store idempotency records in database:

```go
type IdempotencyRecord struct {
    ID           string    `json:"id" db:"id"`
    Key          string    `json:"key" db:"idempotency_key"`
    RequestHash  string    `json:"request_hash" db:"request_hash"`
    Parameters   json.RawMessage `json:"parameters" db:"parameters"`
    Response     json.RawMessage `json:"response" db:"response"`
    StatusCode   int       `json:"status_code" db:"status_code"`
    CreatedAt    time.Time `json:"created_at" db:"created_at"`
    ExpiresAt    time.Time `json:"expires_at" db:"expires_at"`
}

type PersistentCache struct {
    redis  *redis.Client
    db     *sql.DB
}

func (pc *PersistentCache) SetResponse(ctx context.Context, idempotencyKey string, response *CachedResponse, requestParams interface{}) error {
    // Store in Redis (fast)
    if err := pc.storeInRedis(ctx, idempotencyKey, response); err != nil {
        return err
    }

    // Also store in database (audit trail)
    record := IdempotencyRecord{
        ID:          generateID(),
        Key:         idempotencyKey,
        RequestHash: hashRequest(requestParams),
        Parameters:  mustMarshal(requestParams),
        Response:    response.Body,
        StatusCode:  response.StatusCode,
        CreatedAt:   time.Now(),
        ExpiresAt:   time.Now().Add(48 * time.Hour),
    }

    _, err := pc.db.ExecContext(ctx, `
        INSERT INTO idempotency_records
        (id, idempotency_key, request_hash, parameters, response, status_code, created_at, expires_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    `, record.ID, record.Key, record.RequestHash, record.Parameters,
        record.Response, record.StatusCode, record.CreatedAt, record.ExpiresAt)

    return err
}
```

---

## Cleanup Job

```go
func (pc *PersistentCache) CleanupExpired(ctx context.Context) error {
    // Delete expired records from database
    result, err := pc.db.ExecContext(ctx, `
        DELETE FROM idempotency_records
        WHERE expires_at < NOW()
    `)

    if err != nil {
        return err
    }

    rows, _ := result.RowsAffected()
    log.Printf("Cleaned up %d expired idempotency records", rows)

    return nil
}

// Run cleanup every hour
func StartCleanupJob(pc *PersistentCache) {
    ticker := time.NewTicker(1 * time.Hour)
    go func() {
        for range ticker.C {
            ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
            pc.CleanupExpired(ctx)
            cancel()
        }
    }()
}
```

---

## Monitoring

```go
type IdempotencyMetrics struct {
    cacheHits      prometheus.Counter
    cacheMisses    prometheus.Counter
    conflicts      prometheus.Counter
    errors         prometheus.Counter
}

var metrics = &IdempotencyMetrics{
    cacheHits: prometheus.NewCounter(prometheus.CounterOpts{
        Name: "idempotency_cache_hits_total",
        Help: "Number of idempotency cache hits",
    }),
    cacheMisses: prometheus.NewCounter(prometheus.CounterOpts{
        Name: "idempotency_cache_misses_total",
        Help: "Number of idempotency cache misses",
    }),
    conflicts: prometheus.NewCounter(prometheus.CounterOpts{
        Name: "idempotency_conflicts_total",
        Help: "Number of parameter hash conflicts",
    }),
}

func (c *AtomicCache) TryLockWithValidation(...) {
    // ... existing logic ...

    if cached != nil {
        metrics.cacheHits.Inc()
    } else {
        metrics.cacheMisses.Inc()
    }

    if conflictErr != nil {
        metrics.conflicts.Inc()
    }
}
```

---

## Common Pitfalls

### 1. Forgetting to Restore Body

```go
// ❌ WRONG: Body consumed, can't read again
body, _ := io.ReadAll(r.Body)
hash := hash(body)

// ✅ RIGHT: Restore body
body, _ := io.ReadAll(r.Body)
r.Body = io.NopCloser(bytes.NewReader(body))
```

### 2. Using Non-Cryptographic Hash

```go
// ❌ WRONG: Collisions possible
hash := fnv.Sum32(body)  // Only 32 bits!

// ✅ RIGHT: Use SHA-256
hash := sha256.Sum256(body)  // 256 bits, negligible collision chance
```

### 3. Including Unstable Fields in Hash

```go
// ❌ WRONG: Timestamp changes every time
hashInput{Timestamp: time.Now()}

// ✅ RIGHT: Only business logic fields
hashInput{Amount: 100, Currency: "USD"}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's the optimal TTL for idempotency keys? (24-48 hours)
2. Why use different TTL for success vs failure? (Allow retry on client error)
3. Why persist to database? (Audit trail, compliance)
4. How do you clean up expired keys? (Background job, Redis TTL)
5. What fields should be included in request hash? (Business logic fields only)

---

**Ready for the complete solution? Read `solution.md`**
