# Solution: Database Deadlock - Inconsistent Lock Ordering

---

## Root Cause

**Locks acquired in inconsistent order** depending on business logic:

```
Payment A→X: Lock(A) → Lock(X)
Payment X→A: Lock(X) → Lock(A)

When simultaneous: Circular wait → Deadlock!
```

The code locked rows in the order of business operations (user first, then merchant), not in a globally consistent order.

---

## Immediate Fixes

### Fix 1: Consistent Lock Ordering

```go
func ProcessPayment(db *sql.DB, userID, merchantID int64, amount float64) error {
    tx, _ := db.Begin()
    defer tx.Rollback()

    // ALWAYS lock in consistent order (lower ID first)
    firstID, secondID := userID, merchantID
    if userID > merchantID {
        firstID, secondID = merchantID, userID
    }

    // Lock both rows upfront (prevent deadlocks)
    rows, _ := tx.Query(`
        SELECT id, balance
        FROM users
        WHERE id IN ($1, $2)
        FOR UPDATE
    `, firstID, secondID)

    // Parse results
    var users = map[int64]float64{}
    for rows.Next() {
        var id int64
        var balance float64
        rows.Scan(&id, &balance)
        users[id] = balance
    }

    // Check balance and update
    if users[userID] < amount {
        return errors.New("insufficient funds")
    }

    // Now safe to update
    tx.Exec("UPDATE users SET balance = balance - $1 WHERE id = $2", amount, userID)
    tx.Exec("UPDATE users SET balance = balance + $1 WHERE id = $2", amount, merchantID)

    // Record transaction
    tx.Exec(`INSERT INTO transactions (user_id, merchant_id, amount, created_at)
             VALUES ($1, $2, $3, NOW())`,
        userID, merchantID, amount)

    return tx.Commit()
}
```

### Fix 2: Application-Level Locking

For systems where consistent ordering is complex:

```go
// Use distributed lock (Redis, etcd)
lockKey := fmt.Sprintf("payment_lock:%d:%d", userID, merchantID)
lock := redis.AcquireLock(lockKey, 30*time.Second)
defer lock.Release()

// Now process payment
ProcessPayment(db, userID, merchantID, amount)
```

---

## Long-term Solutions

### Solution 1: Account Ledger Pattern

Instead of modifying balances directly, use an immutable ledger:

```sql
CREATE TABLE accounts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    current_balance BIGINT NOT NULL  -- Denominated in cents
);

CREATE TABLE ledger_entries (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts(id),
    amount BIGINT NOT NULL,           -- Positive for credit, negative for debit
    reference_id UUID NOT NULL,       -- Idempotency key
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX ledger_reference_idx ON ledger_entries(reference_id);
CREATE INDEX ledger_account_created_idx ON ledger_entries(account_id, created_at DESC);
```

When processing a payment:

```sql
BEGIN;

-- 1. Add debit entry (idempotent)
INSERT INTO ledger_entries (account_id, amount, reference_id)
VALUES
    ((SELECT id FROM accounts WHERE user_id = $1), -$3, $5)
ON CONFLICT (reference_id) DO NOTHING;

-- 2. Add credit entry (idempotent)
INSERT INTO ledger_entries (account_id, amount, reference_id)
VALUES
    ((SELECT id FROM accounts WHERE user_id = $2), $3, $5)
ON CONFLICT (reference_id) DO NOTHING;

-- 3. Update balances (single statement, no row-level locks needed)
WITH debits AS (
    SELECT account_id, SUM(amount) as total
    FROM ledger_entries
    WHERE reference_id = $5 AND amount < 0
    GROUP BY account_id
),
credits AS (
    SELECT account_id, SUM(amount) as total
    FROM ledger_entries
    WHERE reference_id = $5 AND amount > 0
    GROUP BY account_id
)
UPDATE accounts a
SET current_balance = a.current_balance +
    COALESCE((SELECT total FROM debits WHERE debits.account_id = a.id), 0) +
    COALESCE((SELECT total FROM credits WHERE credits.account_id = a.id), 0)
WHERE a.id IN (SELECT account_id FROM debits)
   OR a.id IN (SELECT account_id FROM credits);

COMMIT;
```

**Benefits:**
- Single UPDATE statement per account → no cross-row deadlocks
- Immutable audit trail
- Idempotent operations

### Solution 2: Queue-Based Processing

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   API       │     │  Payment    │     │   Worker    │
│  Endpoint   │────▶│    Queue    │────▶│   (Single   │
└─────────────┘     └─────────────┘     │  Threaded)  │
                                        └─────────────┘
```

With a single-threaded worker:
- No concurrent transactions
- No deadlocks possible
- Trade-off: Lower throughput

### Solution 3: Partition by Account

Shard users by account ID:

```
Shard 0: users 0-999,999      → Single DB connection
Shard 1: users 1,000,000-1,999,999
...
```

Transactions within a shard use consistent ordering. Cross-shard transactions handled asynchronously.

---

## Systemic Prevention (Staff Level)

### 1. Deadlock Monitoring

```sql
-- Track deadlock frequency
SELECT
  date_trunc('hour', now()) as hour,
  COUNT(*) as deadlocks
FROM pg_stat_database_deadlocks
GROUP BY hour
HAVING COUNT(*) > 10;  -- Alert threshold
```

### 2. Code Review Checklist

Any code using `FOR UPDATE` must:
- [ ] Lock rows in consistent order (e.g., by ID)
- [ ] Use `IN (...)` with `FOR UPDATE` for multiple rows
- [ ] Keep transactions short (< 100ms)
- [ ] Have retry logic for deadlocks

### 3. Deadlock-Testing Framework

```go
// Test that runs concurrent cross-transactions
func TestCrossPaymentDeadlock(t *testing.T) {
    var wg sync.WaitGroup
    errors := make(chan error, 2)

    // Start two concurrent cross-payments
    wg.Add(2)

    go func() {
        defer wg.Done()
        if err := ProcessPayment(db, 1, 2, 100); err != nil {
            errors <- err
        }
    }()

    go func() {
        defer wg.Done()
        if err := ProcessPayment(db, 2, 1, 100); err != nil {
            errors <- err
        }
    }()

    wg.Wait()
    close(errors)

    // Should have no errors (especially not deadlock errors)
    for err := range errors {
        if err != nil {
            t.Errorf("Payment failed: %v", err)
        }
    }
}
```

---

## Real Incident

**Stripe (2016)**: Payment processing deadlocks during peak hours. Root cause: Locks acquired in inconsistent order. Fix: Implemented consistent lock ordering and moved to account ledger pattern.

---

## Jargon

| Term | Definition |
|------|------------|
| **Deadlock** | Two+ transactions waiting for each other's locks; database kills one |
| **Circular wait** | Condition where T1 waits for T2, T2 waits for T3 ... Tn waits for T1 |
| **Lock ordering** | Strategy to always acquire locks in consistent order (e.g., by ID) |
| **FOR UPDATE** | PostgreSQL clause locking rows until transaction ends |
| **Ledger pattern** | Immutable transaction log; balances computed from entries |
| **Idempotent** | Operation can be applied multiple times with same result |
| **Partitioning** | Splitting data by key to avoid cross-partition transactions |

---

## Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| **Consistent lock ordering** | Simple, no architecture change | Doesn't work for complex multi-row locks |
| **Application locking** | Works across databases | Single point of failure (Redis), extra latency |
| **Ledger pattern** | Audit trail, idempotent, no deadlocks | More complex, requires balance recomputation |
| **Queue-based** | No concurrency, simple | Lower throughput, eventual consistency |
| **Partitioning** | Isolates hotspots, scalable | Cross-partition transactions complex |

For payment systems: **Ledger pattern + consistent lock ordering** is best.

---

**Next Problem:** `intermediate/incident-014-sli-breach/`
