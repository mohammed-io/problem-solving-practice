---
name: postgres-107-generated-columns
description: Generated Columns vs Triggers
difficulty: Advanced
category: PostgreSQL / Schema Design
level: Principal Engineer
---
# PostgreSQL 107: Generated Columns vs Triggers

---

## The Situation

Your team needs a `full_name` column combining `first_name` and `last_name`:

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL
);
```

**Current approach:** Triggers

```sql
CREATE OR REPLACE FUNCTION update_full_name()
RETURNS TRIGGER AS $$
BEGIN
    NEW.full_name := NEW.first_name || ' ' || NEW.last_name;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_full_name_trigger
    BEFORE INSERT OR UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_full_name();
```

---

## The Incident Report

```
Issue: Bulk insert taking 10x longer than expected

Original query:
INSERT INTO users (first_name, last_name)
SELECT first_name, last_name FROM staging_users;
-- 100,000 rows: 2 seconds expected, 20 seconds actual

Root cause: Trigger firing for every row
```

---

## What are Generated Columns?

PostgreSQL 12+ feature: Columns computed from other columns.

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    full_name VARCHAR(201) GENERATED ALWAYS AS (first_name || ' ' || last_name) STORED
);
```

**Benefits:**
- Computed automatically (no trigger)
- Can be STORED (computed on write) or VIRTUAL (computed on read)
- No trigger overhead

---

## Trigger vs Generated Column

| Aspect | Trigger | Generated Column |
|--------|---------|-----------------|
| Performance | Per-row overhead | Inline computation |
| Transparency | Hidden logic | Visible in schema |
| Indexing | Need trigger for index | Can index directly |
| Overhead | Function call per row | Minimal |

---

## The Question

Should you use triggers or generated columns for:

1. `full_name = first_name || ' ' || last_name`
2. `total = price * quantity`
3. `display_name = COALESCE(nickname, first_name)`
4. `age = EXTRACT(YEAR FROM AGE(dob))`
5. `searchable = to_tsvector(title || ' ' || content)`

---

**When you've thought about it, read `step-01.md**
