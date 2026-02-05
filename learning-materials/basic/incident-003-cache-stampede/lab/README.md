# Cache Stampede Lab

Hands-on lab demonstrating cache stampede and mitigation strategies.

## The Problem

Cache stampede occurs when cached data expires and multiple clients simultaneously:
1. Check cache → MISS
2. Compute expensive query (all at once!)
3. Update cache

This overwhelms the backend.

## Quick Start

```bash
# Start Redis and client
docker-compose up -d

# Run experiments
docker-compose run --rm client python scripts/client.py
```

## Strategies Compared

| Strategy | Stampede | Latency | Complexity |
|----------|----------|---------|------------|
| No Caching | 🚨 Yes (N computations) | High | Low |
| Naive Cache | 🚨 Yes (race condition) | Low | Low |
| Lock-Based | ✅ Prevented (1 computation) | Medium | Medium |
| Early Expiration | ⚠️ Reduces (probabilistic) | Low | Medium |
| Request Coalescing | ✅ Prevented (1 computation) | Low | High |

## Experiments

### 1. No Caching
All 5 clients compute independently. 5 computations = stampede!

### 2. Naive Caching
All check cache, miss, and compute together. Still a stampede!

### 3. Lock-Based
First client gets lock, computes once. Others wait and get cache.

### 4. Early Expiration
Cache expires slightly early; one client refreshes proactively.

### 5. Request Coalescing
Waiting clients share a single computation result.

## Cleanup

```bash
docker-compose down
```
