# Solution: Generated Columns vs Triggers

---

## Root Cause

**Triggers have significant per-row overhead** due to PL/pgSQL invocation. Generated columns compute inline.

---

## When to Use Generated Columns

### Use Cases for GENERATED ALWAYS

```sql
-- 1. Concatenation
full_name VARCHAR GENERATED ALWAYS AS (first_name || ' ' || last_name) STORED

-- 2. Arithmetic
total DECIMAL GENERATED ALWAYS AS (price * quantity) STORED

-- 3. Coalesce
display_name VARCHAR GENERATED ALWAYS AS (COALESCE(nickname, first_name)) STORED

-- 4. Date math
expiry_date DATE GENERATED ALWAYS AS (created_at + INTERVAL '1 year') STORED

-- 5. JSON extraction
email_domain VARCHAR GENERATED ALWAYS AS (split_part(email, '@', 2)) STORED

-- 6. Conditional
status VARCHAR GENERATED ALWAYS AS (
    CASE
        WHEN active THEN 'active'
        WHEN deleted_at IS NOT NULL THEN 'deleted'
        ELSE 'suspended'
    END
) STORED
```

### Use Cases for Triggers

```sql
-- 1. Side effects (update other tables)
CREATE TRIGGER update_stock
AFTER INSERT OR UPDATE ON order_items
FOR EACH ROW
BEGIN
    UPDATE products
    SET stock = stock - NEW.quantity,
        last_order_at = NOW()
    WHERE id = NEW.product_id;
END;

-- 2. Complex validation
CREATE TRIGGER check_business_hours
BEFORE INSERT ON appointments
FOR EACH ROW
BEGIN
    IF EXTRACT(DOW FROM NEW.scheduled_at) IN (0, 6) THEN
        RAISE EXCEPTION 'No appointments on weekends';
    END IF;

    IF EXTRACT(HOUR FROM NEW.scheduled_at) < 9 OR EXTRACT(HOUR FROM NEW.scheduled_at) > 17 THEN
        RAISE EXCEPTION 'Outside business hours';
    END IF;
END;

-- 3. Audit logging
CREATE TRIGGER log_changes
AFTER UPDATE ON users
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (table_name, record_id, old_value, new_value, changed_at)
    VALUES ('users', OLD.id, row_to_json(OLD), row_to_json(NEW), NOW());
END;
```

---

## Migration Strategy

```sql
-- Migrate from trigger to generated column

-- Step 1: Add generated column
ALTER TABLE users
ADD COLUMN full_name_generated VARCHAR(201)
GENERATED ALWAYS AS (first_name || ' ' || last_name) STORED;

-- Step 2: Backfill data
UPDATE users
SET full_name_generated = first_name || ' ' || last_name;

-- Step 3: Rename columns (switch)
ALTER TABLE users RENAME COLUMN full_name TO full_name_old;
ALTER TABLE users RENAME COLUMN full_name_generated TO full_name;

-- Step 4: Drop old column and trigger
ALTER TABLE users DROP COLUMN full_name_old;
DROP TRIGGER update_full_name_trigger ON users;
DROP FUNCTION update_full_name();
```

---

## Performance Benchmarks

```
Operation: 100,000 inserts

Trigger:      15 seconds
Generated:     1.5 seconds
No overhead:   1.2 seconds

Generated adds ~25% overhead vs no computed column
Trigger adds ~1100% overhead vs no computed column
```

---

## Trade-offs

| Aspect | Generated Column | Trigger |
|--------|------------------|---------|
| Performance | Inline, minimal overhead | Per-row function call |
| Complexity | Expressions only | Full PL/pgSQL |
| Transparency | Visible in schema | Hidden in trigger |
| Side effects | None (read-only) | Can update other tables |
| External state | Not accessible | Can call external APIs |

**Recommendation:** Use generated columns for all derived data. Use triggers only for side effects and complex validation.

---

**Next Problem:** `real-world/incident-200-github-mysql/`
