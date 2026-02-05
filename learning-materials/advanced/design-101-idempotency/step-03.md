# Step 03: Atomic Check-and-Set

---

## Solution: Redis SET NX

Redis has an atomic operation: `SET key value NX TTL`

- **NX** = Only set if key doesn't exist
- **TTL** = Auto-expire after time

This is **atomic** - no race condition possible!

---

## Visual: Atomic vs Non-Atomic

```
❌ NON-ATOMIC (race condition):
Request A: GET key → nil
Request B: GET key → nil
Request A: Process payment
Request B: Process payment
Request A: SET key result
Request B: SET key result
Result: Double charge!

✅ ATOMIC (SET NX):
Request A: SET key value NX → success (first)
Request B: SET key value NX → failure (key exists)
Request B: GET key → return cached result
Result: Single charge!
```

---

## Implementation: Atomic Lock

```go
package idempotency

import (
    "context"
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "fmt"
    "time"

    "github.com/redis/go-redis/v9"
)

const (
    LockPrefix     = "idempotency:lock:"
    DataPrefix     = "idempotency:data:"
    LockTTL        = 30 * time.Second   // Lock expires after 30s
    DataTTL        = 48 * time.Hour     // Data expires after 48h
)

type AtomicCache struct {
    client *redis.Client
}

// Try to acquire lock atomically
// Returns true if lock acquired (first request)
// Returns false with cached data if lock exists (retry)
func (c *AtomicCache) TryLock(ctx context.Context, idempotencyKey string) (bool, *CachedResponse, error) {
    lockKey := LockPrefix + idempotencyKey

    // Atomic: SET if not exists
    acquired, err := c.client.SetNX(ctx, lockKey, "1", LockTTL).Result()
    if err != nil {
        return false, nil, err
    }

    if !acquired {
        // Lock exists: get cached response
        return c.getCached(ctx, idempotencyKey)
    }

    return true, nil, nil  // Lock acquired, proceed to process
}

// Store the final response
func (c *AtomicCache) SetResponse(ctx context.Context, idempotencyKey string, response *CachedResponse) error {
    lockKey := LockPrefix + idempotencyKey
    dataKey := DataPrefix + idempotencyKey

    // Store response data
    data, err := json.Marshal(response)
    if err != nil {
        return err
    }

    pipe := c.client.Pipeline()

    // Store response
    pipe.Set(ctx, dataKey, data, DataTTL)

    // Remove lock (optional - let it expire naturally)
    pipe.Del(ctx, lockKey)

    _, err = pipe.Exec(ctx)
    return err
}

func (c *AtomicCache) getCached(ctx context.Context, idempotencyKey string) (bool, *CachedResponse, error) {
    dataKey := DataPrefix + idempotencyKey

    data, err := c.client.Get(ctx, dataKey).Result()
    if err == redis.Nil {
        // Lock exists but no data yet (still processing)
        return false, nil, fmt.Errorf("request still processing")
    }
    if err != nil {
        return false, nil, err
    }

    var response CachedResponse
    if err := json.Unmarshal([]byte(data), &response); err != nil {
        return false, nil, err
    }

    return false, &response, nil  // Return cached
}
```

---

## Payment Handler with Atomic Lock

```go
func (h *PaymentHandler) Charge(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()
    idempotencyKey := r.Header.Get("Idempotency-Key")
    if idempotencyKey == "" {
        http.Error(w, "Missing Idempotency-Key", http.StatusBadRequest)
        return
    }

    // Try to acquire lock atomically
    acquired, cached, err := h.cache.TryLock(ctx, idempotencyKey)
    if err != nil {
        http.Error(w, "Cache error", http.StatusInternalServerError)
        return
    }

    // If we have cached data, return it
    if !acquired && cached != nil {
        writeResponse(w, cached)
        return
    }

    // If lock not acquired and no cache, request is still processing
    if !acquired {
        http.Error(w, "Request still processing", http.StatusAccepted)
        return
    }

    // Parse request
    var payment Payment
    if err := json.NewDecoder(r.Body).Decode(&payment); err != nil {
        http.Error(w, "Invalid request", http.StatusBadRequest)
        return
    }

    // Process payment
    result, err := h.gateway.Charge(ctx, payment)
    if err != nil {
        // On failure, remove lock to allow retry
        h.cache.ReleaseLock(ctx, idempotencyKey)
        http.Error(w, err.Error(), http.StatusBadRequest)
        return
    }

    // Store response
    response := &CachedResponse{
        StatusCode: http.StatusOK,
        Body:       mustMarshal(result),
    }
    h.cache.SetResponse(ctx, idempotencyKey, response)

    writeResponse(w, response)
}

func (c *AtomicCache) ReleaseLock(ctx context.Context, idempotencyKey string) {
    lockKey := LockPrefix + idempotencyKey
    c.client.Del(ctx, lockKey)
}
```

---

## What if Processing Crashes?

```
Problem: Service crashes after acquiring lock
Result: Lock stuck for 30 seconds

Solution: TTL auto-expires lock
→ After 30s, new request can proceed
→ Old request is forgotten
```

---

## Quick Check

Before moving on, make sure you understand:

1. What does SET NX do? (Set only if key doesn't exist)
2. Why is SET NX atomic? (Single Redis operation)
3. What happens if lock exists but no data? (Request still processing)
4. What if service crashes? (Lock expires after TTL)
5. Should we delete lock on success? (Optional, let it expire)

---

**Ready to handle parameter changes? Read `step-04.md`**
