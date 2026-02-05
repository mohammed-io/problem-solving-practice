# Solution: Distributed Deadlock - Lock Ordering + Idempotency

---

## Root Cause

**Three compounding issues:**

1. **Inconsistent lock ordering** → Circular wait across services
2. **Unsafe lock implementation** → Locks without expiry, unsafe unlock
3. **No idempotency** → Duplicate transfers on crash/retry

---

## Complete Solution

### 1. Global Lock Ordering

```go
type OrderedLock struct {
    redis *redis.Client
}

func (ol *OrderedLock) AcquireLocks(keys ...string) (func(), error) {
    // Sort keys to ensure consistent order globally
    sortedKeys := make([]string, len(keys))
    copy(sortedKeys, keys)
    sort.Strings(sortedKeys)

    var tokens []string
    for _, key := range sortedKeys {
        token, err := ol.acquireLock(key)
        if err != nil {
            // Failed: release all acquired locks
            ol.releaseLocks(sortedKeys, tokens)
            return nil, err
        }
        tokens = append(tokens, token)
    }

    // Return cleanup function
    return func() {
        ol.releaseLocks(sortedKeys, tokens)
    }, nil
}

func (ol *OrderedLock) acquireLock(key string) (string, error) {
    token := uuid.New().String()
    lockKey := "lock:" + key

    // Atomic SETNX with expiry
    script := `
        if redis.call("exists", KEYS[1]) == 0 then
            redis.call("setex", KEYS[1], ARGV[1], ARGV[2])
            return 1
        else
            return 0
        end
    `

    result, err := ol.redis.Eval(context.Background(), script,
        []string{lockKey}, 30, token).Result()

    if err != nil {
        return "", err
    }
    if result.(int64) == 0 {
        return "", errors.New("lock already held")
    }
    return token, nil
}

func (ol *OrderedLock) releaseLocks(keys []string, tokens []string) {
    for i, key := range keys {
        token := tokens[i]
        script := `
            if redis.call("get", KEYS[1]) == ARGV[1] then
                redis.call("del", KEYS[1])
            end
        `
        ol.redis.Eval(context.Background(), script,
            []string{"lock:" + key}, token)
    }
}
```

### 2. Idempotent Transfer with Intent Recording

```go
type TransferService struct {
    db          *sql.DB
    lockManager *OrderedLock
}

type TransferIntent struct {
    IdempotencyKey string
    FromAccount    string
    ToAccount      string
    Amount         float64
    Status         string  // "pending", "completed", "failed"
    CreatedAt      time.Time
    CompletedAt    *time.Time
}

func (ts *TransferService) Transfer(
    idempotencyKey, fromAccount, toAccount string,
    amount float64,
) error {
    // Start transaction
    tx, _ := ts.db.Begin()
    defer tx.Rollback()

    // Check if already processed
    var status string
    err := tx.QueryRow(`
        SELECT status FROM transfer_intents
        WHERE idempotency_key = $1
    `, idempotencyKey).Scan(&status)

    if err == sql.ErrNoRows {
        // New transfer: record intent
        _, err = tx.Exec(`
            INSERT INTO transfer_intents
            (idempotency_key, from_account, to_account, amount, status, created_at)
            VALUES ($1, $2, $3, $4, 'pending', NOW())
        `, idempotencyKey, fromAccount, toAccount, amount)
    } else if err == nil && status == "completed" {
        // Already processed - idempotent!
        return nil
    }

    // Acquire locks in consistent order
    cleanup, err := ts.lockManager.AcquireLocks(fromAccount, toAccount)
    if err != nil {
        return err
    }
    defer cleanup()

    // Check balance
    var balance float64
    tx.QueryRow("SELECT balance FROM accounts WHERE id = $1 FOR UPDATE", fromAccount).
        Scan(&balance)

    if balance < amount {
        tx.Exec("UPDATE transfer_intents SET status = 'failed' WHERE idempotency_key = $1",
            idempotencyKey)
        return tx.Commit()
    }

    // Perform transfer
    tx.Exec("UPDATE accounts SET balance = balance - $1 WHERE id = $2", amount, fromAccount)
    tx.Exec("UPDATE accounts SET balance = balance + $1 WHERE id = $2", amount, toAccount)

    // Mark complete
    tx.Exec(`
        UPDATE transfer_intents
        SET status = 'completed', completed_at = NOW()
        WHERE idempotency_key = $1
    `, idempotencyKey)

    return tx.Commit()
}
```

### 3. Database Schema for Idempotency

```sql
CREATE TABLE transfer_intents (
    id BIGSERIAL PRIMARY KEY,
    idempotency_key VARCHAR(100) UNIQUE NOT NULL,
    from_account VARCHAR(50) NOT NULL,
    to_account VARCHAR(50) NOT NULL,
    amount DECIMAL(19,4) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_intents_key ON transfer_intents(idempotency_key);
CREATE INDEX idx_intents_status ON transfer_intents(status, created_at);
```

---

## Alternative: Two-Phase Commit

For true distributed transactions across services:

```
Phase 1 (Prepare):
  Service A: Prepare transfer (lock A, write intent)
  Service B: Prepare credit (lock B, write intent)
  Coordinator: Collect votes

Phase 2 (Commit):
  If all voted YES:
    Service A: Commit
    Service B: Commit
  Else:
    Service A: Rollback
    Service B: Rollback
```

**Complex but necessary** for cross-service transactions.

---

## Alternative: Saga Pattern

Break transfer into compensatable steps:

```go
type SagaStep struct {
    Execute   func() error
    Compensate func() error
}

func TransferSaga(from, to string, amount float64) error {
    steps := []SagaStep{
        {
            Execute:   func() error { return Debit(from, amount) },
            Compensate: func() error { return Credit(from, amount) },
        },
        {
            Execute:   func() error { return Credit(to, amount) },
            Compensate: func() error { return Debit(to, amount) },
        },
    }

    completed := 0
    for i, step := range steps {
        if err := step.Execute(); err != nil {
            // Compensate completed steps
            for j := i - 1; j >= 0; j-- {
                steps[j].Compensate()
            }
            return err
        }
        completed++
    }
    return nil
}
```

---

## Systemic Prevention

### 1. Deadlock Detection

```go
// Build wait-for graph periodically
type WaitForGraph struct {
    nodes map[string]bool
    edges map[string][]string
}

func DetectDeadlock(wfg *WaitForGraph) []string {
    // Use Tarjan's algorithm to find cycles
    // If cycle found, kill one transaction in cycle
}
```

### 2. Lock Timeout Monitoring

```promql
# Alert on locks held too long
- alert: LockHeldTooLong
  expr: |
    redis_lock_duration_seconds{quantile="0.99"} > 30
  labels:
    severity: critical
```

### 3. Idempotency Key Enforcement

```go
// Middleware enforcing idempotency keys
func IdempotencyMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        idempotencyKey := r.Header.Get("Idempotency-Key")
        if idempotencyKey == "" && r.Method != "GET" {
            http.Error(w, "Idempotency-Key required", 400)
            return
        }
        next.ServeHTTP(w, r)
    })
}
```

---

## Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| **Lock ordering** | Simple, effective | Requires global ordering |
| **Distributed locks (Redis)** | Fast, scalable | Single point of failure, complexity |
| **Two-phase commit** | Correct, atomic | Slow, blocking, complex |
| **Saga pattern** | Available, compensatable | Eventually consistent, complex |

**Recommendation:** Lock ordering + idempotency for single-service transfers. Saga for cross-service workflows.

---

## Real Incident Reference

**AWS DynamoDB (2012):** Distributed deadlock in sharded system. Fixed with consistent lock ordering and improved timeout handling.

**Stripe (2018):** Duplicate payment issue due to crashes before idempotency recording. Fixed by storing intent before any action.

---

## Jargon

| Term | Definition |
|------|------------|
| **Distributed deadlock** | Deadlock across multiple services; no global coordinator |
| **Circular wait** | Process A waits for B, B waits for C, ..., N waits for A |
| **Lock ordering** | Always acquire locks in consistent order to prevent deadlock |
| **Idempotency key** | Unique identifier for operation; makes retries safe |
| **Two-phase commit** | Protocol for atomic distributed transactions |
| **Saga** | Pattern for long-lived transactions with compensation |
| **Wait-for graph** | Graph showing which processes wait for which resources |
| **Compensating transaction** | Undo operation for saga step |

---

**Next Problem:** `advanced/incident-101-cascade-failure/`
