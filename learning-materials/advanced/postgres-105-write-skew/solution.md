# Solution: Write Skew - Serializable Isolation and Alternative Designs

---

## Root Cause

**REPEATABLE READ isolation doesn't prevent write skew.** Both transactions read same snapshot, validate independently, concurrent updates violate constraint.

---

## Complete Solution

### Solution 1: SERIALIZABLE Isolation

```sql
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
BEGIN;
SELECT total_tickets, sold_tickets FROM tickets WHERE event_id = 1 FOR UPDATE;
-- Check and update
COMMIT;
```

**How it works:** PostgreSQL adds predicate locks on WHERE conditions. If two transactions predicate-lock overlapping sets, one must abort.

**Trade-off:** More contention, possible serialization failures requiring retry.

### Solution 2: Recheck in UPDATE

```python
def book_ticket(event_id, quantity):
    tx = db.begin(isolation_level="SERIALIZABLE")

    try:
        # Lock and get current state
        result = tx.execute(
            "SELECT sold_tickets FROM tickets WHERE event_id = %s FOR UPDATE",
            event_id
        ).fetchone()

        # Recheck constraint in UPDATE
        updated = tx.execute(
            """UPDATE tickets
               SET sold_tickets = sold_tickets + %s
               WHERE event_id = %s
                 AND sold_tickets + %s <= total_tickets
               RETURNING sold_tickets""",
            quantity, event_id, quantity
        ).fetchone()

        if updated is None:
            tx.rollback()
            raise SoldOutError()

        tx.commit()
        return updated.sold_tickets

    except SerializationFailure:
        # Retry with exponential backoff
        return retry_with_backoff(book_ticket, event_id, quantity)
```

### Solution 3: Single-Row Counter

```sql
CREATE TABLE ticket_inventory (
    event_id INT PRIMARY KEY,
    available INT NOT NULL,
    version INT NOT NULL DEFAULT 1
);

-- Atomic decrement
UPDATE ticket_inventory
SET available = available - 1,
    version = version + 1
WHERE event_id = $1
  AND available > 0
RETURNING available, version;
```

**If UPDATE returns 0 rows:** No available tickets (or wrong version).

### Solution 4: Materialize Constraint

```sql
-- Add computed column for remaining
CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    event_id INT NOT NULL,
    total_tickets INT NOT NULL,
    sold_tickets INT NOT NULL DEFAULT 0,
    remaining INT GENERATED ALWAYS AS (total_tickets - sold_tickets) STORED,
    CHECK (remaining >= 0)
);

-- Now update is simpler
UPDATE tickets
SET sold_tickets = sold_tickets + 1
WHERE event_id = $1 AND remaining > 0;
```

**Benefits:**
- Constraint enforced at database level
- Single UPDATE checks constraint atomically
- No application-level logic needed

---

## Detection

```sql
-- Monitor for serialization failures
SELECT
    datname,
    query,
    calls,
    rollbacks
FROM pg_stat_statements
WHERE query LIKE '%INSERT INTO tickets%'
  OR query LIKE '%UPDATE tickets%';
```

```promql
- alert: HighSerializationFailures
  expr: |
    rate(postgresql_serialization_failures_total[5m]) > 0.1
  labels:
    severity: warning
```

---

## Trade-offs

| Solution | Pros | Cons |
|----------|------|------|
| **SERIALIZABLE** | Correct, prevents skew | Lower throughput, retries |
| **Recheck in UPDATE** | Application control | Requires careful coding |
| **Single-row counter** | Simple, atomic | Requires schema change |
| **Materialized constraint** | DB enforces, simple | Storage overhead, compute on write |

**Recommendation:** For critical constraints (like inventory), use atomic counters or materialized constraints with CHECK.

---

**Next Problem:** `advanced/postgres-106-foreign-key-cascade/`
