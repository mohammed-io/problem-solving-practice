# Solution: Idempotency Keys

---

## Complete Implementation

```go
package idempotency

import (
    "context"
    "crypto/sha256"
    "encoding/json"
    "fmt"
    "time"

    "github.com/go-redis/redis/v8"
)

type IdempotencyService struct {
    redis *redis.Client
}

type RequestResult struct {
    Response interface{}
    Status   int
    Headers  map[string]string
}

func (is *IdempotencyService) Process(
    ctx context.Context,
    idempotencyKey string,
    requestParams interface{},
    handler func() (*RequestResult, error),
) (*RequestResult, error) {
    key := fmt.Sprintf("idempotency:%s", idempotencyKey)

    // Hash request parameters
    paramsJSON, _ := json.Marshal(requestParams)
    paramsHash := sha256.Sum256(paramsJSON)

    // Lua script for atomic check-and-set
    script := `
        local key = KEYS[1]
        local params_hash = ARGV[1]

        local existing = redis.call("GET", key)
        if existing then
            local existing_data = cjson.decode(existing)
            if existing_data.params_hash == params_hash then
                -- Same key, same params: return cached
                return existing_data
            else
                -- Same key, different params: conflict
                return {error = "REQUEST_CONFLICT", existing_params = existing_data.params_hash}
            end
        end

        -- Key doesn't exist, set as "processing"
        redis.call("SETEX", key, 86400, cjson.encode({
            status = "processing",
            params_hash = params_hash
        }))
        return nil
    `

    result, err := is.redis.Eval(ctx, script, []string{key},
        fmt.Sprintf("%x", paramsHash)).Result()

    if err != nil {
        return nil, err
    }

    // Check if we got cached result
    if result != nil {
        if resultMap, ok := result.(map[string]interface{}); ok {
            if _, hasError := resultMap["error"]; hasError {
                return nil, fmt.Errorf("request conflict: same key with different parameters")
            }
            if resultMap["response"] != nil {
                // Return cached response
                return unmarshalResult(resultMap)
            }
        }
    }

    // Process the actual request
    requestResult, err := handler()
    if err != nil {
        // On failure, remove key to allow retry
        is.redis.Del(ctx, key)
        return nil, err
    }

    // Store successful result
    storedData := map[string]interface{}{
        "status":      "completed",
        "params_hash": fmt.Sprintf("%x", paramsHash),
        "response":    requestResult.Response,
        "status_code": requestResult.Status,
        "headers":     requestResult.Headers,
        "created_at":  time.Now().Unix(),
    }

    storedJSON, _ := json.Marshal(storedData)
    is.redis.Set(ctx, key, storedJSON, 48*time.Hour)

    return requestResult, nil
}

func unmarshalResult(data map[string]interface{}) (*RequestResult, error) {
    return &RequestResult{
        Response: data["response"],
        Status:   int(data["status_code"].(float64)),
        Headers:  data["headers"].(map[string]string),
    }, nil
}
```

---

## Key Design Decisions

### 1. Request Hashing

Same idempotency key with different parameters = conflict error.

```http
# First request
POST /payments
Idempotency-Key: abc-123
{ "amount": 1000, "currency": "usd" }

# Retry (same params) - OK
POST /payments
Idempotency-Key: abc-123
{ "amount": 1000, "currency": "usd" }

# Different params - ERROR
POST /payments
Idempotency-Key: abc-123
{ "amount": 2000, "currency": "usd" }  # Different amount!
```

### 2. TTL Management

- **Processing keys:** 24 hour TTL (prevent stuck keys)
- **Completed keys:** 48 hour TTL (longer for audit trail)

### 3. Failure Handling

On handler failure, remove key to allow retry:

```go
requestResult, err := handler()
if err != nil {
    // Remove key - allow client to retry
    is.redis.Del(ctx, key)
    return nil, err
}
```

**Exception:** For "non-retryable" errors (like validation errors), keep the key to prevent infinite retries.

---

## Trade-offs

| Aspect | Option A | Option B |
|--------|----------|----------|
| **Storage** | Redis only | Redis + DB |
| **TTL** | 24 hours | 48 hours |
| **Conflict** | Return error | Ignore and use new params |
| **Failure behavior** | Delete key | Keep key with error |

**Recommendation:** Redis with 48h TTL, delete on retryable failures, keep on non-retryable.

---

## Real Implementation

**Stripe idempotency keys:**
- Key format: Client-provided string
- TTL: 24 hours for keys, 90 days for stored results
- Conflict: Returns error on same key with different params

---

**Next Problem:** `advanced/postgres-100-mvcc-revealed/`
