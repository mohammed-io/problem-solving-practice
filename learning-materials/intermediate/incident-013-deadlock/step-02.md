# Step 2: Understand the Root Cause

---

## Root Cause

**Locks are acquired in inconsistent order:**

1. Transaction 1: Lock user A → Lock merchant X
2. Transaction 2: Lock user X → Lock merchant A

When A→X and X→A happen simultaneously:
- T1 holds lock A, needs lock X
- T2 holds lock X, needs lock A
- **Deadlock!**

---

## Why Only During Peak Hours?

During low traffic:
- Probability of A→X and X→A running simultaneously = low
- When they do overlap, one usually completes before the other starts

During peak traffic:
- Many concurrent payments
- High probability of "cross" payments occurring simultaneously
- Deadlocks become frequent

---

## The Solution: Consistent Lock Ordering

**Always acquire locks in the same order**, regardless of business logic:

```go
// BEFORE: Inconsistent order
tx.QueryRow("SELECT ... WHERE id = $1 FOR UPDATE", userID)      // User first
tx.QueryRow("SELECT ... WHERE id = $1 FOR UPDATE", merchantID)  // Merchant second

// AFTER: Consistent order (always lock lower ID first)
firstID, secondID := userID, merchantID
if userID > merchantID {
    firstID, secondID = merchantID, userID
}

tx.QueryRow("SELECT ... WHERE id = $1 FOR UPDATE", firstID)   // Lower ID
tx.QueryRow("SELECT ... WHERE id = $1 FOR UPDATE", secondID)  // Higher ID
```

Now both transactions lock in the same order:
- T1 (A→X): Lock min(A,X) → Lock max(A,X)
- T2 (X→A): Lock min(X,A) → Lock max(X,A)

**No circular wait possible!**

---

## Questions

1. **Is consistent lock ordering enough?** (What about other operations that lock these rows?)

2. **What if you need to lock more than 2 rows?** (How do you order 3+ locks?)

3. **Are there any downsides to this approach?** (Think about business logic)

---

## Quick Check

Before moving on, make sure you understand:

1. What's the solution to deadlock? (Consistent lock ordering - always lock in same order)
2. How do you order locks with 2+ rows? (Always lock lower ID first, or sort IDs before locking)
3. Why does consistent ordering prevent circular wait? (Both transactions acquire locks in same order, no cycle possible)
4. Is consistent ordering enough? (Need all operations that lock rows to follow same rule)
5. What's a potential downside? (Business logic might be less intuitive)

---

**When you've considered the trade-offs, read `solution.md`**
