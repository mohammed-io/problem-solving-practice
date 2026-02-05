# Step 2: Solutions to Write Skew

---

## Solution 1: SERIALIZABLE Isolation Level

```sql
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;

BEGIN;
SELECT total_tickets, sold_tickets FROM tickets WHERE event_id = 1 FOR UPDATE;
-- [Checks and updates]
COMMIT;
```

**SERIALIZABLE adds predicate locking:**

```
Transaction A:
- Predicate locks "WHERE event_id = 1"
- Updates row
- Commits

Transaction B:
- Predicate locks "WHERE event_id = 1"
- But predicate conflicts with A's predicate!
- B must wait for A to complete
- When A commits, B's serialization check fails
- B must retry
```

**Cost:** More contention, retries, lower throughput.

---

## Solution 2: Explicit Lock with Recheck

```sql
BEGIN;
-- Lock in UPDATE order
SELECT total_tickets, sold_tickets FROM tickets WHERE event_id = 1 FOR UPDATE;

-- After acquiring lock, recheck condition
UPDATE tickets
SET sold_tickets = sold_tickets + $1
WHERE event_id = $2
  AND sold_tickets + $1 <= total_tickets  -- Recheck!
RETURNING sold_tickets;

-- If UPDATE affected 0 rows, rollback
COMMIT;
```

**Why this helps:**
- UPDATE acquires lock
- WHERE clause rechecks constraint after lock acquired
- If constraint violated, UPDATE affects 0 rows
- Application can detect and retry

---

## Solution 3: Atomic Counter

```sql
-- Use single-row counter, not separate columns
CREATE TABLE ticket_counters (
    event_id INT PRIMARY KEY,
    sold_count INT NOT NULL DEFAULT 0,
    total_count INT NOT NULL
);

-- Book atomically
UPDATE ticket_counters
SET sold_count = sold_count + $1
WHERE event_id = $2
  AND sold_count + $1 <= total_count
RETURNING sold_count;
```

**If UPDATE returns 0 rows:** Sold out!

---

## Quick Check

Before moving on, make sure you understand:

1. What does SERIALIZABLE do? (Adds predicate locking, prevents write skew)
2. What's the cost of SERIALIZABLE? (More contention, retries, lower throughput)
3. How does explicit lock with recheck work? (Recheck constraint in WHERE after lock)
4. What's an atomic counter pattern? (Single UPDATE with condition in WHERE)
5. Which solution is best? (Depends: SERIALIZABLE for correctness, atomic counter for high throughput)

---

**Continue to `solution.md`**
