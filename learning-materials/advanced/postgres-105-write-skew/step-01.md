# Step 1: Understanding Snapshot Isolation

---

## The Timeline with Snapshots

```
Initial: sold_tickets = 50

T1: Transaction A begins (snapshot: sold_tickets = 50)
T2: Transaction B begins (snapshot: sold_tickets = 50)
    Both have same snapshot!

T3: A checks 50 + 50 <= 100 → OK
T4: B checks 50 + 60 <= 100 → OK
    Both see their snapshot's value (50)

T5: A updates to 100
T6: B updates to 110

T7: A commits → writes 100
T8: B commits → writes 110 (overwrites A's write!)

Both validations passed, but result violates constraint!
```

---

## Why FOR UPDATE Doesn't Prevent Write Skew

```sql
-- Transaction A
BEGIN;
SELECT total_tickets, sold_tickets FROM tickets WHERE event_id = 1 FOR UPDATE;
-- Returns (100, 50), locks the row

-- Transaction B
BEGIN;
SELECT total_tickets, sold_tickets FROM tickets WHERE event_id = 1 FOR UPDATE;
-- Waits for A...

A commits, releases lock
B proceeds: But B's snapshot still shows 50!
B checks: 50 + 60 <= 100 → Passes!
B updates: sold_tickets = 110
```

**The row lock only serializes access to the row.** It doesn't update B's snapshot to see A's changes because B's snapshot was taken at BEGIN (REPEATABLE READ) or at first SELECT (READ COMMITTED).

---

## Quick Check

Before moving on, make sure you understand:

1. What is write skew? (Two transactions update based on same stale snapshot, violate constraint)
2. Why does snapshot isolation allow write skew? (Both transactions see same snapshot, both validate)
3. Why doesn't FOR UPDATE prevent write skew? (Locks row, but doesn't update snapshot)
4. What's the difference between READ COMMITTED and REPEATABLE READ? (Snapshot per statement vs per transaction)
5. Why do both validations pass? (Both check against their snapshot's value, not current state)

---

**Continue to `step-02.md`**
