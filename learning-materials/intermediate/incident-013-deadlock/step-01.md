# Step 1: Analyze the Lock Pattern

---

## Hint

Look at the code again. Pay attention to the **order of lock acquisition**:

```go
// Transaction 1: User A pays Merchant X
tx.QueryRow("SELECT ... FROM users WHERE id = A FOR UPDATE")  // Lock A
tx.QueryRow("SELECT ... FROM users WHERE id = X FOR UPDATE")  // Lock X

// Transaction 2: User X pays Merchant A (simultaneous)
tx.QueryRow("SELECT ... FROM users WHERE id = X FOR UPDATE")  // Lock X
tx.QueryRow("SELECT ... FROM users WHERE id = A FOR UPDATE")  // Lock A
```

**What happens when both transactions execute at the same time?**

---

## Diagram

```
Transaction 1 (A→X)    Transaction 2 (X→A)
─────────────────────   ─────────────────────
Lock row A              Lock row X
                        │
   Wait for X ──────────┘         ← BLOCKED
   │
   └─────────── Wait for A        ← BLOCKED

   ↻  CIRCULAR WAIT  ↺
```

---

## Questions

1. **If both transactions always locked rows in the same order (e.g., always lock lower ID first), would this deadlock still occur?**

2. **What's the difference between "user A pays merchant X" and "user X pays merchant A" versus "user A pays merchant X" and "user B pays merchant X"?**

---

## Quick Check

Before moving on, make sure you understand:

1. What's a deadlock? (Two transactions each waiting for the other's lock)
2. What causes deadlock in the payment code? (Locks acquired in inconsistent order)
3. What's circular wait? (T1 holds A needs X, T2 holds X needs A)
4. Why does deadlock happen more during peak hours? (Higher probability of cross transactions)
5. What's consistent lock ordering? (Always lock rows in same order, like lower ID first)

---

**When you have a theory, read `step-02.md`**
