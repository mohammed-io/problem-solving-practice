# Solution: Zero-Downtime Schema Migration

---

## Root Cause

**ALTER TABLE with DEFAULT** rewrites entire table, requiring ACCESS EXCLUSIVE lock.

---

## Complete Solution

### The pgextwensible Approach

```sql
-- Phase 1: Add column without default (instant)
ALTER TABLE orders ADD COLUMN status VARCHAR(20);

-- Phase 2: Backfill in batches (no long-held locks)
CREATE OR REPLACE FUNCTION backfill_orders_status(batch_size INT)
RETURNS VOID AS $$
DECLARE
    min_id BIGINT;
    max_id BIGINT;
    updated INT;
BEGIN
    SELECT MIN(id), MAX(id) INTO min_id, max_id FROM orders;

    WHILE min_id <= max_id LOOP
        UPDATE orders
        SET status = COALESCE(status, 'pending')
        WHERE id >= min_id AND id < min_id + batch_size;

        GET DIAGNOSTICS updated = ROW_COUNT;
        min_id := min_id + batch_size;

        COMMIT;  -- Commit each batch
        RAISE NOTICE 'Backfilled % rows up to ID %', updated, min_id - 1;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Run backfill
SELECT backfill_orders_status(10000);

-- Phase 3: Add default (instant now)
ALTER TABLE orders ALTER COLUMN status SET DEFAULT 'pending';

-- Phase 4: Add NOT NULL (after verification)
ALTER TABLE orders ALTER COLUMN status SET NOT NULL;

-- Phase 5: Add index (concurrent)
CREATE INDEX CONCURRENTLY idx_orders_status ON orders(status);
```

### Application Changes

```python
# Version 1 (before migration)
class Order:
    def __init__(self, id, user_id, total_amount):
        self.id = id
        self.user_id = user_id
        self.total_amount = total_amount

# Version 2 (handle NULL status)
class Order:
    def __init__(self, id, user_id, total_amount, status=None):
        self.id = id
        self.user_id = user_id
        self.total_amount = total_amount
        self.status = status or 'pending'  # Backward compatible

# Version 3 (status required)
class Order:
    def __init__(self, id, user_id, total_amount, status):
        self.id = id
        self.user_id = user_id
        self.total_amount = total_amount
        self.status = status  # Required field
```

### Deployment Order

```
1. Deploy Version 2 code (handles NULL status)
2. Run ALTER TABLE orders ADD COLUMN status (NULL)
3. Run backfill batches (background job)
4. Add default: ALTER TABLE ... SET DEFAULT 'pending'
5. Verify: SELECT COUNT(*) FROM orders WHERE status IS NULL
6. Add NOT NULL constraint
7. Deploy Version 3 code (requires status)
```

---

## Checklist for Zero-Downtime Migrations

### Before Migration

1. **Can operation be done online?**
   - CREATE INDEX CONCURRENTLY: Yes
   - ADD COLUMN (no default): Yes
   - ADD COLUMN (with default): No (need workaround)

2. **Is backward compatibility handled?**
   - Old code works with new schema?
   - New code works with old schema?

3. **What's the rollback plan?**
   - Can migration be reversed?
   - Can code be rolled back independently?

### During Migration

1. **Monitor backfill progress**
2. **Verify data integrity**
3. **Check for long-running transactions blocking ALTER**

### After Migration

1. **Remove compatibility code**
2. **Update documentation**
3. **Run ANALYZE** (update statistics)

---

## Other Migration Patterns

### Adding Column with Non-NULL Default (Large Table)

```sql
-- Wrong: Locks table for hours
ALTER TABLE big_table ADD COLUMN status VARCHAR(20) DEFAULT 'pending' NOT NULL;

-- Right: Multi-step approach
-- 1. Add nullable (instant)
ALTER TABLE big_table ADD COLUMN status VARCHAR(20);

-- 2. Backfill (batches)
UPDATE big_table SET status = 'pending' WHERE ctid IN (
    SELECT ctid FROM big_table WHERE status IS NULL LIMIT 10000
);

-- 3. Add default (instant)
ALTER TABLE big_table ALTER COLUMN status SET DEFAULT 'pending';

-- 4. NOT NULL after backfill complete
ALTER TABLE big_table ALTER COLUMN status SET NOT NULL;
```

### Renaming Column

```sql
-- Never rename directly! Breaks all application code
ALTER TABLE orders RENAME COLUMN status TO order_status;

-- Instead: Add new column, migrate, deprecate old
-- 1. Add new column
ALTER TABLE orders ADD COLUMN order_status VARCHAR(20);

-- 2. Trigger to keep in sync
CREATE OR REPLACE FUNCTION sync_order_status()
RETURNS TRIGGER AS $$
BEGIN
    NEW.order_status = NEW.status;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER sync_order_status_trigger
    BEFORE INSERT OR UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION sync_order_status();

-- 3. Migrate application code to use new column
-- 4. Drop trigger, drop old column
```

---

**Next Problem:** `advanced/postgres-104-cursor-pagination/`
