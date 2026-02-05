# Solution: Amazon CQRS Cassandra Outage

## Answers to Questions

### 1. Why Did CL=QUORUM Not Prevent Stale Reads?

**Answer: QUORUM doesn't guarantee all replicas are up-to-date**

With RF=3, QUORUM=2:
- During partition: AZ-B + AZ-C formed quorum
- AZ-A was isolated with stale data
- Reads could hit AZ-A + one other replica
- If AZ-A hasn't received writes yet → stale data!

**The misconception:**
```
CL=QUORUM means "majority of replicas acknowledge"
NOT "all replicas have latest data"

If replica 1 & 2 acknowledge write:
- Replica 3 might be stale
- Read hitting replica 3 + replica 1: QUORUM achieved!
- But replica 3 has old data
```

---

### 2. Is CQRS with Read Cache Inherently AP?

**Answer: Yes, if read cache is distributed**

CQRS separates write and read models:
- Write side: Usually strong consistency (PostgreSQL)
- Read side: Usually eventual consistency (Cassandra, Redis)

**The AP nature comes from:**
1. Async replication from write to read side
2. Read side can serve stale data during sync delay
3. Partition affects read side differently than write side

**Mitigation strategies:**
- Fallback to write side on read failures
- Version stamps to detect staleness
- TTL for cached data
- Circuit breaker to fail fast

---

### 3. How Could System Detect Partition and Fail Fast?

**Answer: Multiple detection methods**

**1. Health checks:**
```python
def is_cassandra_healthy():
    try:
        # Check if all replicas responsive
        status = nodetool.status()
        if status.down_count > 0:
            return False

        # Check write latency
        latency = measure_write_latency()
        if latency > THRESHOLD_MS:
            return False

        return True
    except Exception:
        return False
```

**2. Circuit breaker:**
```python
class CassandraCircuitBreaker:
    def __init__(self):
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN

    def call(self, operation):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > TIMEOUT:
                self.state = 'HALF_OPEN'
            else:
                raise CircuitBreakerOpen()

        try:
            result = operation()
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
            self.failure_count = 0
            return result
        except Exception:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count > THRESHOLD:
                self.state = 'OPEN'
            raise
```

**3. Quorum reachability check:**
```python
def can_achieve_quorum():
    # Check if enough replicas are responsive
    peers = nodetool.netstats().peers
    responsive = sum(1 for p in peers if p.is_responsive)
    return responsive >= (RF // 2 + 1)
```

---

### 4. Correct Use Case for Hinted Handoff?

**When it's safe:**
- Short-term partitions (seconds to minutes)
- Low write volume
- Hint storage sufficient for backlog
- Application can tolerate some delay

**When it's dangerous:**
- Long partitions (hint storage fills up)
- High write volume (hints overflow)
- No monitoring for dropped hints
- No dead letter queue

**Best practices:**
```yaml
# cassandra.yaml
max_hints_per_thread: 2048
max_hints_delivery_threads: 8
hinted_handoff_enabled: true
hinted_handoff_throttle_delay_ms: 0
```

**Monitor:**
```bash
# Check hint storage
nodetool statshints

# Alert if:
# - Hints > 80% of max
# - Hints not decreasing (replay stalled)
# - Dropped mutations > 0
```

---

### 5. Redesign to Handle Partitions Correctly

```python
class ResilientCQRS:
    """
    Improved architecture:
    1. Write side: PostgreSQL (source of truth)
    2. Read side: Cassandra (cache, CL=LOCAL_QUORUM)
    3. Fallback: Direct read from PostgreSQL
    4. DLQ: Failed writes for replay
    5. Monitoring: Health checks + circuit breakers
    """

    def __init__(self):
        self.write_db = PostgreSQLClient()
        self.read_db = CassandraClient(CL=LOCAL_QUORUM)
        self.dlq = SQSClient('cassandra-dlq')
        self.circuit_breaker = CircuitBreaker(threshold=5, timeout=60)
        self.health_checker = CassandraHealthChecker()

    def write_order(self, order):
        """Write side: Always consistent"""
        try:
            # Write to PostgreSQL (source of truth)
            order_id = self.write_db.insert(
                "INSERT INTO orders VALUES (?, ?)",
                order.id, order.data
            )

            # Publish event for read side
            self.event_bus.publish('OrderCreated', order_id, order.data)

            return order_id

        except Exception as e:
            # Write failure = system unavailable
            logger.error(f"Failed to write order: {e}")
            raise

    def get_order(self, order_id):
        """Read side: Fallback to PostgreSQL on issues"""
        # Check health first
        if not self.health_checker.is_healthy():
            logger.warning("Cassandra unhealthy, falling back to PostgreSQL")
            return self._read_from_postgres(order_id)

        try:
            # Try with circuit breaker
            return self.circuit_breaker.call(
                lambda: self.read_db.get(order_id)
            )

        except (Timeout, Unavailable) as e:
            logger.warning(f"Cassandra unavailable: {e}")
            return self._read_from_postgres(order_id)

    def _read_from_postgres(self, order_id):
        """Fallback: Read from source of truth"""
        return self.write_db.query(
            "SELECT * FROM orders WHERE id = ?",
            order_id
        )

    def update_read_cache(self, order):
        """Async update of read cache from events"""
        try:
            self.read_db.insert(
                "INSERT INTO orders VALUES (?, ?)",
                order.id, order.data
            )
        except Exception as e:
            # Don't fail! Write to DLQ for replay
            self.dlq.send({
                'order': order,
                'error': str(e),
                'timestamp': time.time()
            })
            metrics.increment('cassandra.write_failed')
```

**Key improvements:**
1. **Health checking** - detect issues before they cascade
2. **Circuit breaker** - fail fast instead of hanging
3. **Fallback to PostgreSQL** - source of truth always available
4. **DLQ for failures** - no silent data loss
5. **LOCAL_QUORUM** - single-region consistency, faster recovery
6. **Async cache updates** - don't block writes

---

## Root Cause Summary

| Failure Mode | What Happened | Fix |
|--------------|---------------|-----|
| Hot partition | Uneven load caused node A to fail first | Use consistent hashing |
| Hint overflow | Silent data loss when hints full | Add DLQ + monitoring |
| CL=ONE panic | Made reads MORE stale | Fallback to PostgreSQL |
| No partition detection | Served stale data unknowingly | Health checks + circuit breaker |
| SSTable bloat | Compaction couldn't keep up | Reduce write amplification |

---

## Key Takeaways

1. **CL=QUORUM ≠ Strong Consistency** - majority can still be stale
2. **CQRS read caches are inherently AP** - plan for fallback
3. **Hinted handoff has limits** - monitor and add DLQ
4. **Fail fast is better than stale** - circuit breakers essential
5. **Source of truth must be available** - fallback strategy required
