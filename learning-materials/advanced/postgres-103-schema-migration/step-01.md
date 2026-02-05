# Step 1: The Default Value Problem

---

## Why DEFAULT is Slow

```sql
ALTER TABLE orders ADD COLUMN status VARCHAR(20) DEFAULT 'pending';
```

**PostgreSQL must rewrite EVERY row:**

```
Before: After:
[row1] [row1, status='pending']
[row2] [row2, status='pending']
...
[10M rows updated]
```

This requires:
- Scanning entire table
- Rewriting each row
- Updating all indexes
- Holding ACCESS EXCLUSIVE lock the whole time

---

## Faster: Add NULL Column First

```sql
-- Step 1: Add column without default (FAST)
ALTER TABLE orders ADD COLUMN status VARCHAR(20);

-- Result: Instant! No table rewrite.
-- All rows have NULL status.

-- Step 2: Update rows in batches
UPDATE orders SET status = 'pending' WHERE id = 1;
UPDATE orders SET status = 'pending' WHERE id > 1 AND id <= 1000;
...

-- Step 3: Add default (FAST now, no rows rewritten)
ALTER TABLE orders ALTER COLUMN status SET DEFAULT 'pending';
```

**But:** New rows get default, old rows still NULL. Need application code to handle NULL.

---

## Quick Check

Before moving on, make sure you understand:

1. Why is adding a DEFAULT column slow? (Rewrites every row, holds exclusive lock)
2. What's the faster approach? (Add NULL column, backfill in batches, then set default)
3. Why is ALTER TABLE with NULL fast? (Metadata only change, no table rewrite)
4. What's the tradeoff of the faster approach? (Application must handle NULL temporarily)
5. How does the migration ensure zero downtime? (Incremental changes, backward-compatible code)

---

**Continue to `step-02.md`**
