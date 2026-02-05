# Write Skew Lab

Hands-on lab demonstrating write skew anomaly and how to prevent it.

## The Problem

Write skew occurs when two transactions read the same data concurrently, make decisions based on it, and their updates violate a constraint.

## Quick Start

```bash
# Start PostgreSQL
docker-compose up -d

# Run experiments
docker-compose run --rm client python scripts/client.py
```

## Experiments

### 1. Write Skew Anomaly
Two users booking tickets concurrently:
- Both see 100 tickets available
- User A books 60
- User B books 50
- **Result: 110 tickets sold! 🚨**

### 2. Fix with SERIALIZABLE
Using SERIALIZABLE isolation + FOR UPDATE prevents the anomaly.

### 3. Isolation Comparison
Compare REPEATABLE READ vs SERIALIZABLE behavior.

## Key Takeaways

| Isolation | Write Skew | Performance | Use When |
|-----------|-----------|-------------|----------|
| READ COMMITTED | Possible | Fast | General purpose |
| REPEATABLE READ | Possible | Medium | Default in Postgres |
| SERIALIZABLE | Prevented | Slower | Critical constraints |

## Cleanup

```bash
docker-compose down -v
```
