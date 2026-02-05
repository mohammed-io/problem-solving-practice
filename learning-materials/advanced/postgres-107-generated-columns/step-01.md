# Step 1: Performance Comparison

---

## Trigger Overhead

```sql
CREATE TABLE users_trigger (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    full_name VARCHAR(201)
);

CREATE TRIGGER ... BEFORE INSERT OR UPDATE ...

-- Benchmark
EXPLAIN ANALYZE
INSERT INTO users_trigger (first_name, last_name)
SELECT 'John', 'Doe'
FROM generate_series(1, 100000);

Result: 15 seconds (100k rows)
```

**What happens:**
- For EACH row, trigger function called
- PL/pgSQL interpreter invoked
- Context switches between executor and trigger
- Significant overhead

---

## Generated Column Performance

```sql
CREATE TABLE users_generated (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    full_name VARCHAR(201) GENERATED ALWAYS AS (first_name || ' ' || last_name) STORED
);

-- Benchmark
EXPLAIN ANALYZE
INSERT INTO users_generated (first_name, last_name)
SELECT 'John', 'Doe'
FROM generate_series(1, 100000);

Result: 1.5 seconds (100k rows)
```

**What happens:**
- Expression evaluated inline during INSERT
- No function call overhead
- Direct value computation

---

**10x faster!**

---

## Quick Check

Before moving on, make sure you understand:

1. Why are triggers slow? (PL/pgSQL interpreter, context switches, per-row overhead)
2. Why are generated columns faster? (Inline computation, no function call overhead)
3. What's the performance difference? (~10x faster for generated columns)
4. What's the benchmark result? (15s trigger vs 1.5s generated for 100k rows)
5. Why does the trigger have overhead? (For EACH row, interpreter invocation, context switches)

---

**Continue to `step-02.md`**
