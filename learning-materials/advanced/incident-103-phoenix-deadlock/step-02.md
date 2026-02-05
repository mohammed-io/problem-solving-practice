# Step 2: Breaking the Phoenix Cycle

---

## Solution 1: Global Lock Ordering

Force all transactions to lock in a globally consistent order:

```go
func AcquireLocksSorted(resources []string) error {
    // Sort to ensure consistent order
    sorted := make([]string, len(resources))
    copy(sorted, resources)
    sort.Strings(sorted)

    for _, resource := range sorted {
        if !lockManager.TryAcquire(transactionID, resource) {
            // Release all acquired locks
            for _, r := range acquired {
                lockManager.Release(transactionID, r)
            }
            return errors.New("couldn't acquire all locks")
        }
        acquired = append(acquired, resource)
    }
    return nil
}
```

Now all transactions lock in sorted order. No circular wait possible.

---

## Solution 2: Wait-Die Scheme

Older transactions wait, younger transactions die (abort):

```go
func AcquireWithWaitDie(resource string, txTimestamp int64) error {
    holder := lockManager.GetHolder(resource)

    if holder != nil && holder.timestamp < txTimestamp {
        // Holder is older → we die
        return ErrAbort
    }

    // Holder is younger (or none) → we wait
    return lockManager.Acquire(resource)
}
```

**Why this helps:** Younger transactions abort. Older transactions (closer to completion) continue. Eventually, oldest transaction completes.

---

## Solution 3: Exponential Backoff on Retry

```go
func RetryWithBackoff(tx Transaction) error {
    attempts := 0
    backoff := 100 * time.Millisecond

    for attempts < 10 {
        err := tx.Execute()
        if err == nil {
            return nil
        }

        if errors.Is(err, ErrDeadlock) {
            attempts++
            time.Sleep(backoff)
            backoff *= 2  // Exponential
            continue
        }

        return err
    }

    return ErrMaxRetriesExceeded
}
```

Adding jitter prevents synchronized retries.

---

## Quick Check

Before moving on, make sure you understand:

1. How does global lock ordering prevent phoenix deadlock? (Same order everywhere)
2. What is wait-die scheme? (Older transactions wait, younger abort)
3. Why does wait-die prevent starvation? (Oldest transaction always completes)
4. What's exponential backoff for? (Prevent synchronized retries after abort)
5. Why add jitter to backoff? (Prevent thundering herd on retry)

---

**Continue to `solution.md`**
