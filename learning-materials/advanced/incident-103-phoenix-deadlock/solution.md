# Solution: Phoenix Deadlock - Structural Recovery

---

## Root Cause

**Inconsistent lock ordering** across transactions causes repeated deadlocks on retry.

Victim selection doesn't help because the victim retries with **same lock order**, causing the same deadlock.

---

## Complete Solution

### Solution 1: Global Lock Ordering (Recommended)

```go
type Transaction struct {
    id          string
    resources   []string
    acquired    []string
    timestamp   int64
}

func (tx *Transaction) AcquireLocks() error {
    // CRITICAL: Sort resources globally
    sorted := make([]string, len(tx.resources))
    copy(sorted, tx.resources)
    sort.Strings(sorted)

    for _, resource := range sorted {
        if !lockManager.TryAcquire(tx.id, resource) {
            // Release all acquired locks
            tx.ReleaseAll()
            return ErrCouldNotAcquire
        }
        tx.acquired = append(tx.acquired, resource)
    }

    return nil
}
```

**Why this works:** All transactions lock in same order. No circular wait possible.

### Solution 2: Wait-Die Scheme

```go
type LockManager struct {
    locks map[string]*Lock
}

type Lock struct {
    holder    string
    timestamp int64
    waiters   []string
}

func (lm *LockManager) Acquire(txID string, resource string, txTimestamp int64) error {
    lm.mu.Lock()
    defer lm.mu.Unlock()

    lock := lm.locks[resource]

    if lock == nil {
        // No holder: acquire
        lm.locks[resource] = &Lock{holder: txID, timestamp: txTimestamp}
        return nil
    }

    if lock.timestamp < txTimestamp {
        // Holder is older: we die (abort)
        return ErrAbortTransaction
    }

    // Holder is younger: we wait
    lock.waiters = append(lock.waiters, txID)
    return nil
}
```

**Why this works:** Older transactions eventually complete. Younger transactions abort. System makes progress.

### Solution 3: Wound-Wait Scheme

```go
func (lm *LockManager) AcquireWoundWait(txID string, resource string, txTimestamp int64) error {
    lock := lm.locks[resource]

    if lock == nil {
        lm.locks[resource] = &Lock{holder: txID, timestamp: txTimestamp}
        return nil
    }

    if lock.timestamp > txTimestamp {
        // Holder is younger: wound it (abort holder)
        lm.Abort(lock.holder)
        // Now acquire
        lm.locks[resource] = &Lock{holder: txID, timestamp: txTimestamp}
        return nil
    }

    // Holder is older: we wait
    lock.waiters = append(lock.waiters, txID)
    return nil
}
```

**Why this works:** Older transactions aren't kept waiting by younger ones.

---

## Trade-offs

| Scheme | Pros | Cons |
|--------|------|------|
| **Global ordering** | Simple, no deadlocks | Requires knowing all locks upfront |
| **Wait-die** | Progress guaranteed, no starvation | Young transactions may starve |
| **Wound-wait** | Older transactions never wait | Complex, requires aborting others |

---

## Real Incident Reference

Phoenix deadlock is a well-known problem in distributed database research. First described in the 1980s, still relevant today.

**Key insight:** Deadlock detection + naive retry = phoenix deadlock. Need structural fixes (lock ordering, wait-die, wound-wait).

---

**Next Problem:** `advanced/design-100-consistent-hash/`
