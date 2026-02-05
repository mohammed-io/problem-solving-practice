# Step 1: MVCC Snapshots

---

## When is Snapshot Taken?

**READ COMMITTED (default):**
- Snapshot taken at **each statement**, not transaction start
- Sees changes committed before current statement

**REPEATABLE READ:**
- Snapshot taken at **first SELECT** in transaction
- All statements see same snapshot

**Example:**

```sql
-- Session 1
BEGIN;
UPDATE accounts SET balance = 900 WHERE id = 1;
-- Don't commit

-- Session 2 (READ COMMITTED)
BEGIN;
SELECT balance FROM accounts WHERE id = 1;  -- Sees 1000
-- (Session 1 commits)
SELECT balance FROM accounts WHERE id = 1;  -- Sees 900!
COMMIT;

-- Session 3 (REPEATABLE READ)
BEGIN;
SELECT balance FROM accounts WHERE id = 1;  -- Sees 1000
-- (Session 1 commits)
SELECT balance FROM accounts WHERE id = 1;  -- Still sees 1000!
COMMIT;
```

---

## Transaction ID Visibility Rules

For a row to be visible to transaction T:

1. **Row's `xmin` must be committed** (and not in T's excluded list)
2. **Row's `xmax` must be 0 (not deleted) OR `xmax` transaction not committed**

**In code (simplified):**
```python
func is_visible(row Row, transaction Transaction) bool {
    // Check xmin (creator)
    if !isCommitted(row.xmin) {
        return false
    }
    if contains(transaction.excluded, row.xmin) {
        return false // Created by future transaction
    }

    // Check xmax (deleter)
    if row.xmax == 0 {
        return true // Not deleted
    }
    if !isCommitted(row.xmax) {
        return true // Delete not committed yet
    }
    if contains(transaction.excluded, row.xmax) {
        return true // Deleted by future transaction
    }

    return false // Deleted by committed transaction
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. When is snapshot taken in READ COMMITTED? (Each statement)
2. When is snapshot taken in REPEATABLE READ? (First SELECT in transaction)
3. What are xmin and xmax? (xmin = creator transaction, xmax = deleter transaction)
4. What makes a row visible? (xmin committed, row not deleted by committed transaction)
5. Why does REPEATABLE READ not see new commits? (Snapshot fixed at first SELECT)

---

**Continue to `step-02.md`**
