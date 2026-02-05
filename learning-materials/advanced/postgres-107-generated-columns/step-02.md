# Step 2: When to Use Each

---

## Use Generated Columns When:

✅ Deterministic (no external state)
✅ Same result every time given same inputs
✅ Pure functions (no side effects)
✅ Performance critical

**Examples:**
```sql
-- Simple concatenation
full_name VARCHAR(201) GENERATED ALWAYS AS (first_name || ' ' || last_name) STORED

-- Calculation
total DECIMAL GENERATED ALWAYS AS (price * quantity) STORED

-- Coalesce
display_name VARCHAR(100) GENERATED ALWAYS AS (COALESCE(nickname, first_name)) STORED

-- Date math
expiry_date DATE GENERATED ALWAYS AS (created_at + INTERVAL '30 days') STORED
```

---

## Use Triggers When:

✅ Non-deterministic (need external state)
✅ Complex logic (multiple statements)
✅ Side effects (update other tables)
✅ Conditional logic (IF...THEN)

**Examples:**
```sql
-- Complex logic
CREATE TRIGGER update_inventory
AFTER INSERT ON order_items
FOR EACH ROW
BEGIN
    UPDATE products
    SET stock = stock - NEW.quantity
    WHERE id = NEW.product_id;

    IF (SELECT stock FROM products WHERE id = NEW.product_id) < 0 THEN
        RAISE EXCEPTION 'Out of stock';
    END IF;
END;
```

---

## STORED vs VIRTUAL

```sql
-- STORED: Computed on write, takes disk space
full_name VARCHAR(201) GENERATED ALWAYS AS (...) STORED

-- VIRTUAL: Computed on read, no disk space
full_name VARCHAR(201) GENERATED ALWAYS AS (...) VIRTUAL
```

| Type | Write Cost | Read Cost | Storage |
|------|-----------|----------|---------|
| STORED | Higher | Lower | Yes |
| VIRTUAL | Lower | Higher | No |

**Recommendation:** STORED for computed columns used in WHERE/JOIN. VIRTUAL for infrequently accessed.

---

## Quick Check

Before moving on, make sure you understand:

1. When should you use generated columns? (Deterministic, pure functions, performance-critical)
2. When should you use triggers? (Non-deterministic, complex logic, side effects)
3. What's the difference between STORED and VIRTUAL? (STORED = computed on write, VIRTUAL = computed on read)
4. What are examples of good generated columns? (Concatenation, calculations, date math)
5. When is STORED better than VIRTUAL? (When column is used in WHERE/JOIN clauses)

---

**Continue to `solution.md`**
