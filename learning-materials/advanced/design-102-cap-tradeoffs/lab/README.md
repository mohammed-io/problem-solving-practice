# CAP Theorem Lab

Hands-on lab demonstrating CAP theorem tradeoffs with real databases.

## Systems

| System | CAP Position | Consistency | Availability |
|--------|-------------|-------------|--------------|
| **etcd** | CP | Strong | Degraded during partition |
| **Cassandra** | AP (tunable) | Eventual | Always available |
| **MongoDB** | Configurable | Tunable via write concern | Tunable via write concern |

## Quick Start

```bash
# Start all databases
docker-compose up -d

# Wait for systems to be ready (etcd needs ~30s, Cassandra ~60s)
docker-compose ps

# Run experiments
docker-compose run --rm client python scripts/client.py

# Stop when done
docker-compose down -v
```

## Experiments

### Experiment 1: Normal Operations
All nodes healthy, measure baseline latency.

### Experiment 2: Network Partition
Simulate partition by pausing a node:
```bash
# Pause etcd3 (removes it from quorum)
docker pause etcd3

# Run experiment 2 from client
docker-compose run --rm client python scripts/client.py

# Resume
docker unpause etcd3
```

**Expected Results:**
- etcd (CP): Writes fail - quorum lost
- Cassandra (ONE): Writes succeed - AP works
- MongoDB (w=1): Writes succeed - AP mode
- MongoDB (majority): May fail - depends on remaining nodes

### Experiment 3: Consistency Levels
Compare Cassandra consistency levels (ONE vs QUORUM vs ALL).

## Cleanup

```bash
# Stop and remove volumes
docker-compose down -v

# Remove everything
docker-compose down -v --remove-orphans
```
