# Deadlock Lab

Hands-on lab demonstrating database deadlocks and solutions.

## Quick Start

```bash
# Start PostgreSQL
docker-compose up -d

# Run experiments
docker-compose run --rm client python scripts/client.py
```

## Experiments

### 1. Induce Deadlock
Two concurrent transfers in opposite lock order:
- Thread A: Lock account 1 → wait for account 2
- Thread B: Lock account 2 → wait for account 1
- **Result: DEADLOCK**

### 2. Fix with Lock Ordering
Always lock accounts in ID order:
- Thread A: Transfer 1→2 (locks 1, then 2)
- Thread B: Transfer 2→1 (still locks 1, then 2!)
- **Result: No deadlock**

### 3. SELECT FOR UPDATE
Explicitly lock rows in consistent order before updates.

### 4. Retry Logic
Catch deadlock errors and retry with exponential backoff.

## Cleanup

```bash
docker-compose down -v
```
