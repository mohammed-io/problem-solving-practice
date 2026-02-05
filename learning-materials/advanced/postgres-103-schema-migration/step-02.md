# Step 2: The Complete Migration

---

## Zero-Downtime Migration Strategy

### Phase 1: Add Column (NULL, no default)

```sql
-- Instant! No table rewrite
ALTER TABLE orders ADD COLUMN status VARCHAR(20);
```

**Code compatibility:** Old code doesn't know about `status`, ignores it. New code must handle `NULL`.

```python
# Application code (new version)
def get_order(order_id):
    order = db.query("SELECT * FROM orders WHERE id = %s", order_id)
    # Handle NULL status (backwards compatibility)
    if order.status is None:
        order.status = 'pending'  # Default for old rows
    return order
```

### Phase 2: Backfill Data (Batches)

```sql
-- Create function to update in batches
CREATE OR REPLACE FUNCTION backfill_status(batch_size INT, max_id INT)
RETURNS VOID AS $$
BEGIN
    FOR offset IN SELECT generate_series(0, max_id, batch_size) LOOP
        UPDATE orders
        SET status = 'pending'
        WHERE id >= offset AND id < offset + batch_size
          AND status IS NULL;

        COMMIT;  -- Release locks between batches
        RAISE NOTICE 'Backfilled up to ID %', offset + batch_size;
    END LOOP;
END;
$$;

-- Run in batches
SELECT backfill_status(10000, (SELECT MAX(id) FROM orders));
```

### Phase 3: Add Default Constraint

```sql
-- Now all rows have status, can add default safely
ALTER TABLE orders ALTER COLUMN status SET DEFAULT 'pending';
```

### Phase 4: Add NOT NULL (optional, after validation)

```sql
-- First verify no NULLs remain
SELECT COUNT(*) FROM orders WHERE status IS NULL;  -- Should be 0

-- Then add constraint
ALTER TABLE orders ALTER COLUMN status SET NOT NULL;
```

### Phase 5: Add Index (if needed)

```sql
-- CREATE INDEX CONCURRENTLY doesn't block!
CREATE INDEX CONCURRENTLY idx_orders_status ON orders(status);
```

---

## Complete Timeline

```
Week 1: Deploy code that handles NULL status (compatible with old schema)
Week 2: ALTER TABLE orders ADD COLUMN status (NULL) - instant
Week 2: Run backfill batches (background, no locks)
Week 3: ALTER TABLE orders SET DEFAULT 'pending' - instant
Week 4: Verify no NULLs, add NOT NULL constraint
Week 4: CREATE INDEX CONCURRENTLY
Week 5: Remove compatibility code, require status
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's the zero-downtime migration order? (Add NULL → Backfill → Set DEFAULT → NOT NULL → Index)
2. Why deploy code before schema change? (Application must handle NULL new column)
3. What's CREATE INDEX CONCURRENTLY? (Builds index without blocking writes)
4. Why backfill in batches? (Release locks between batches, avoid long transactions)
5. How long does this migration take? (Weeks, but zero downtime for each step)

---

**Continue to `solution.md`**
