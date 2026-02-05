# Step 1: Analyze the Deadlock Pattern

---

## The Deadlock

```
Transfer(user-A, user-B, 100):  Lock(user-A) → [waits for Lock(user-B)]
Transfer(user-B, user-A, 50):   Lock(user-B) → [waits for Lock(user-A)]
                ↑                                              |
                |______________________________________________|
                            Circular wait!
```

Both transfers hold one lock and wait for the other. Forever.

---

## Why Lock Ordering Matters

If both transfers lock in the **same order**, deadlock is impossible:

```go
// Always lock the account with lower ID first
firstAccount, secondAccount := fromAccount, toAccount
if fromAccount > toAccount {
    firstAccount, secondAccount = toAccount, fromAccount
}

Lock(firstAccount)   // Lower ID always locked first
Lock(secondAccount)  // Higher ID always locked second
```

Now:
```
Transfer A→B: Lock(min(A,B)) = Lock(A), Lock(max(A,B)) = Lock(B)
Transfer B→A: Lock(min(B,A)) = Lock(A), Lock(max(B,A)) = Lock(B)

No circular wait possible!
```

---

## But Wait, What About Distributed Locks?

The problem is **distributed**:
- Service 1 handles A→B transfer
- Service 2 handles B→A transfer
- Different machines, different processes

Lock ordering helps locally, but what about across services?

**The answer:** Use a **total order** for all lockable resources across the entire system.

Account IDs must be comparable across all services. If IDs are globally unique and ordered (e.g., UUID lexicographically or database IDs), everyone agrees on lock order.

---

## Quick Check

Before moving on, make sure you understand:

1. What causes deadlock? (Circular wait: A waits for B, B waits for A)
2. How does lock ordering prevent deadlock? (Same order everywhere = no circular wait)
3. What's the challenge with distributed locks? (Different processes must agree on order)
4. What's a "total order" for locks? (All resources have globally comparable IDs)
5. Why is sorting sufficient for deadlock prevention? (Eliminates circular wait condition)

---

**Continue to `step-02.md`**
