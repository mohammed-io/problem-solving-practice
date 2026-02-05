# Step 02: Storage Options and Basic Design

---

## Storage Comparison

| Storage | Pros | Cons | Best For |
|---------|------|------|----------|
| **In-memory map** | Fastest | Lost on restart, doesn't scale | Dev only |
| **Redis** | Fast, TTL built-in, atomic ops | Another dependency | Production |
| **PostgreSQL** | Durable, transactional, indexed | Slower | Compliance, audit |
| **etcd/DynamoDB** | Distributed, consistent | Higher latency | Multi-region |

**Recommendation:** Redis for performance + optional database for audit

---

## Basic Flow

```
1. Client sends: POST /payments
   Header: Idempotency-Key: uuid-v4
   Body: {amount: 100, currency: "USD"}

2. Server checks: Does key exist?
   - Yes: Return cached response
   - No: Continue

3. Process payment (charge card)

4. Store result with key

5. Return response
```

---

## Basic Implementation (Go)

```go
package idempotency

import (
    "context"
    "encoding/json"
    "fmt"
    "time"

    "github.com/redis/go-redis/v9"
)

type IdempotencyCache struct {
    client *redis.Client
    ttl    time.Duration
}

type CachedResponse struct {
    StatusCode int             `json:"status_code"`
    Headers    map[string]string `json:"headers"`
    Body       json.RawMessage   `json:"body"`
}

func NewCache(redisAddr string) *IdempotencyCache {
    return &IdempotencyCache{
        client: redis.NewClient(&redis.Options{
            Addr: redisAddr,
        }),
        ttl: 48 * time.Hour,  // 48 hours default
    }
}

// Check if key exists, return cached response if so
func (c *IdempotencyCache) Get(ctx context.Context, idempotencyKey string) (*CachedResponse, error) {
    key := fmt.Sprintf("idempotency:%s", idempotencyKey)

    data, err := c.client.Get(ctx, key).Result()
    if err == redis.Nil {
        return nil, nil  // Key doesn't exist
    }
    if err != nil {
        return nil, err
    }

    var response CachedResponse
    if err := json.Unmarshal([]byte(data), &response); err != nil {
        return nil, err
    }

    return &response, nil
}

// Store response for idempotency key
func (c *IdempotencyCache) Set(ctx context.Context, idempotencyKey string, response *CachedResponse) error {
    key := fmt.Sprintf("idempotency:%s", idempotencyKey)

    data, err := json.Marshal(response)
    if err != nil {
        return err
    }

    return c.client.Set(ctx, key, data, c.ttl).Err()
}
```

---

## Basic Payment Handler

```go
package payment

import (
    "context"
    "encoding/json"
    "net/http"
)

type PaymentHandler struct {
    cache   *idempotency.IdempotencyCache
    gateway PaymentGateway
}

func (h *PaymentHandler) Charge(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()

    // Extract idempotency key
    idempotencyKey := r.Header.Get("Idempotency-Key")
    if idempotencyKey == "" {
        http.Error(w, "Missing Idempotency-Key", http.StatusBadRequest)
        return
    }

    // Check cache
    cached, err := h.cache.Get(ctx, idempotencyKey)
    if err != nil {
        http.Error(w, "Cache error", http.StatusInternalServerError)
        return
    }
    if cached != nil {
        // Return cached response
        writeResponse(w, cached)
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
        http.Error(w, err.Error(), http.StatusBadRequest)
        return
    }

    // Cache the response
    response := &idempotency.CachedResponse{
        StatusCode: http.StatusOK,
        Body:       mustMarshal(result),
    }
    h.cache.Set(ctx, idempotencyKey, response)

    // Return response
    writeResponse(w, response)
}
```

---

## The Problem: Race Condition

This basic implementation has a race condition!

```
Time | Request A           | Request B
-----|--------------------|---------------------
T1   | cache.Get: nil    |
T2   |                    | cache.Get: nil
T3   | gateway.Charge()   | gateway.Charge()
T4   | cache.Set()        | cache.Set()

Both charged the card!
```

**Need atomic check-and-set!**

---

## Quick Check

Before moving on, make sure you understand:

1. What storage option is best for production? (Redis for speed)
2. What's the basic idempotency flow? (Check cache, process, store)
3. How long should keys persist? (24-48 hours for retries)
4. What's the race condition? (Both requests check before either stores)
5. Why is basic GET then SET not enough? (Not atomic)

---

**Ready to solve the race condition? Read `step-03.md`**
