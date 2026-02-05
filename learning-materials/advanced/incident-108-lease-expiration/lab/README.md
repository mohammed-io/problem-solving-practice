# Distributed Lease Lab

Demonstrates distributed leases and leader election.

## Quick Start

```bash
docker-compose up -d
docker-compose run --rm client python scripts/client.py
```

## Experiments

### 1. etcd Leases
Robust distributed leases with automatic renewal and expiration.

### 2. Redis Leases
Simple locks using SET NX EX. Good for single-Redis setups.

### 3. Leader Election
Distributed leader election using etcd.

### 4. Lease Expiration
What happens when a lease holder crashes?

### 5. Contended Leases
Multiple clients competing for the same lease.

## Cleanup

```bash
docker-compose down
```
