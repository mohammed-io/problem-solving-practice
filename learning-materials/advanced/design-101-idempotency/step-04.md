# Step 04: Handling Parameter Changes

---

## The Problem

What if client uses the same idempotency key but with **different parameters**?

```
Request 1: Idempotency-Key: abc-123
           Body: {amount: 100, currency: "USD"}

Request 2: Idempotency-Key: abc-123  (SAME key!)
           Body: {amount: 200, currency: "USD"}  (DIFFERENT amount!)

Should we:
a) Return cached result from Request 1? (Wrong amount charged!)
b) Process Request 2? (Breaks idempotency contract!)
c) Reject with error? (Safe but requires new key)
```

---

## Solution: Include Request Hash

Include a hash of request parameters in the idempotency check.

```
Key structure:
idempotency:{idempotency-key}:{request_hash}

If client sends same key with different body:
→ Different hash
→ Different Redis key
→ Can detect and reject
```

---

## Implementation: Request Hashing

```go
package idempotency

import (
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "io"
)

// Hash the request body
func hashRequest(body interface{}) (string, error) {
    // Serialize to JSON with sorted keys
    data, err := json.Marshal(body)
    if err != nil {
        return "", err
    }

    // Hash
    hash := sha256.Sum256(data)
    return hex.EncodeToString(hash[:]), nil
}

// Alternative: Hash from HTTP request
func hashHTTPRequest(r *http.Request) (string, error) {
    // Read body
    body, err := io.ReadAll(r.Body)
    if err != nil {
        return "", err
    }

    // Restore body for later reading
    r.Body = io.NopCloser(bytes.NewReader(body))

    // Include relevant headers in hash
    hashInput := struct {
        Method  string
        Headers map[string]string
        Body    string
    }{
        Method: r.Method,
        Headers: map[string]string{
            "Content-Type": r.Header.Get("Content-Type"),
            "Authorization": r.Header.Get("Authorization"),
        },
        Body: string(body),
    }

    data, err := json.Marshal(hashInput)
    if err != nil {
        return "", err
    }

    hash := sha256.Sum256(data)
    return hex.EncodeToString(hash[:]), nil
}
```

---

## Enhanced Cache with Request Validation

```go
type RequestRecord struct {
    RequestHash string          `json:"request_hash"`
    Parameters  json.RawMessage `json:"parameters"`
    Response    *CachedResponse `json:"response"`
}

func (c *AtomicCache) TryLockWithValidation(ctx context.Context, idempotencyKey string, requestBody interface{}) (bool, *CachedResponse, error) {
    requestHash, err := hashRequest(requestBody)
    if err != nil {
        return false, nil, err
    }

    // Check for existing record
    recordKey := fmt.Sprintf("%s%s", DataPrefix, idempotencyKey)
    existingData, err := c.client.Get(ctx, recordKey).Result()

    if err == redis.Nil {
        // No existing record, acquire lock
        return c.acquireLock(ctx, idempotencyKey, requestHash, requestBody)
    }

    if err != nil {
        return false, nil, err
    }

    // Existing record found: validate hash
    var existingRecord RequestRecord
    if err := json.Unmarshal([]byte(existingData), &existingRecord); err != nil {
        return false, nil, err
    }

    if existingRecord.RequestHash != requestHash {
        // Same key, different parameters!
        return false, nil, &ConflictError{
            Message:       "Idempotency key reused with different parameters",
            ExistingHash:  existingRecord.RequestHash,
            ProvidedHash:  requestHash,
        }
    }

    // Same key, same parameters: return cached
    return false, existingRecord.Response, nil
}

func (c *AtomicCache) acquireLock(ctx context.Context, idempotencyKey, requestHash string, requestBody interface{}) (bool, *CachedResponse, error) {
    lockKey := LockPrefix + idempotencyKey

    acquired, err := c.client.SetNX(ctx, lockKey, "1", LockTTL).Result()
    if err != nil {
        return false, nil, err
    }

    if !acquired {
        // Lock exists but no data yet (still processing)
        return false, nil, fmt.Errorf("request still processing")
    }

    // Store pending record
    record := RequestRecord{
        RequestHash: requestHash,
        Parameters:  mustMarshal(requestBody),
    }

    recordKey := fmt.Sprintf("%s%s", DataPrefix, idempotencyKey)
    data, _ := json.Marshal(record)
    c.client.Set(ctx, recordKey, data, LockTTL)

    return true, nil, nil
}

type ConflictError struct {
    Message       string
    ExistingHash  string
    ProvidedHash  string
}

func (e *ConflictError) Error() string {
    return e.Message
}
```

---

## Handler with Parameter Validation

```go
func (h *PaymentHandler) Charge(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()
    idempotencyKey := r.Header.Get("Idempotency-Key")
    if idempotencyKey == "" {
        http.Error(w, "Missing Idempotency-Key", http.StatusBadRequest)
        return
    }

    // Parse request first (we need it for hashing)
    var payment Payment
    if err := json.NewDecoder(r.Body).Decode(&payment); err != nil {
        http.Error(w, "Invalid request", http.StatusBadRequest)
        return
    }

    // Try lock with parameter validation
    acquired, cached, err := h.cache.TryLockWithValidation(ctx, idempotencyKey, payment)

    if err != nil {
        if conflict, ok := err.(*ConflictError); ok {
            // Same key, different parameters
            response := map[string]interface{}{
                "error":   "Idempotency key reused with different parameters",
                "code":    "idempotency_conflict",
                "advice":  "Use a new idempotency key for this request",
            }
            w.Header().Set("Content-Type", "application/json")
            w.WriteHeader(http.StatusConflict)
            json.NewEncoder(w).Encode(response)
            return
        }
        http.Error(w, "Cache error", http.StatusInternalServerError)
        return
    }

    // Return cached if available
    if !acquired && cached != nil {
        writeResponse(w, cached)
        return
    }

    // Lock acquired: process payment
    result, err := h.gateway.Charge(ctx, payment)
    if err != nil {
        h.cache.ReleaseLock(ctx, idempotencyKey)
        http.Error(w, err.Error(), http.StatusBadRequest)
        return
    }

    // Update record with response
    response := &CachedResponse{
        StatusCode: http.StatusOK,
        Body:       mustMarshal(result),
    }
    h.cache.SetResponse(ctx, idempotencyKey, response)

    writeResponse(w, response)
}
```

---

## Design Decision: Reject or Allow?

| Approach | Pros | Cons | Best For |
|----------|------|------|----------|
| **Reject with error** | Safe, explicit | Client needs new key | Financial operations |
| **Allow anyway** | Flexible, easy | Breaks idempotency | Non-critical operations |
| **Merge parameters** | Smart | Complex, ambiguous | Shopping carts |

**Recommendation:** Reject with 409 Conflict for financial operations.

---

## Quick Check

Before moving on, make sure you understand:

1. What's the parameter change problem? (Same key, different body)
2. How does request hashing help? (Detect parameter changes)
3. What should you do if hash differs? (Reject with 409 Conflict)
4. Why store parameters in cache? (For debugging, for conflict detection)
5. What's the recommended approach for payments? (Reject with error)

---

**Ready for production concerns? Read `step-05.md`**
