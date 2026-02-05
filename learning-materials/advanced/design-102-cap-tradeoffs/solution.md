# Solution: CAP Theorem Tradeoffs in Real Systems

## Answers to Questions

### 1. Payment Processing - Which CAP Choice?

**Answer: CP (Consistency over Availability)**

During a partition, CP systems reject operations to preserve consistency. For payments, this means:
- Reject transactions if quorum cannot be reached
- Return 503 Service Unavailable or queue for retry
- Better to fail a payment than allow double-spending

**Real-world examples:**
- Stripe uses PostgreSQL with pessimistic locking
- PayPal uses strongly consistent databases
- Banks use ACID-compliant systems with two-phase commit

---

### 2. Social Media Feed - Is AP Right?

**Answer: Yes, AP is appropriate for feeds**

Feeds can tolerate stale data because:
- Users don't expect real-time perfection
- Occasional duplicates or missing posts are acceptable
- High availability is more important than consistency
- Scale requirements favor AP (1M req/sec)

**Real-world examples:**
- Facebook's TAO (AP graph store for social graph)
- Instagram's feed generation (eventual consistency)
- Twitter's timeline (eventual, with read repair)

---

### 3. How Does DynamoDB Achieve Both AP and CP?

**Answer: Configurable consistency via R + W settings**

DynamoDB uses the NRW formula:
- N = replication factor (3 for most tables)
- R = number of nodes read
- W = number of nodes written

**Strong consistency when R + W > N:**
- W=2, R=2: 2+2=4 > 3 → Strong
- W=3, R=1: 3+1=4 > 3 → Strong

**Eventual consistency when R + W ≤ N:**
- W=1, R=1: 1+1=2 < 3 → Eventual
- W=2, R=1: 2+1=3 = 3 → Eventual (boundary case)

---

### 4. Why is Spanner CP Despite Global Distribution?

**Answer: TrueTime enables global CP**

Google Spanner uses TrueTime API:
- Returns time interval [earliest, latest]
- Uncertainty ε ≈ 10ms (atomic clocks + GPS)
- Commit waits until timestamp + ε < now().latest

This guarantees:
- All commits have globally agreed timestamps
- Reads at timestamp T see ALL commits ≤ T
- External consistency (linearizable) globally!

**Tradeoff:** 50-100ms commit latency vs ~5ms for single-region databases.

---

### 5. Multi-Database Architecture

```python
class MultiDatabaseArchitecture:
    """
    Right tool for each workload:
    - PostgreSQL (CP): Payments, inventory
    - DynamoDB (AP): Social feed, analytics
    - Redis (Session): Shopping cart, user preferences
    - etcd (CP): Configuration, leader election
    """

    def __init__(self):
        # CP: Strong consistency for critical data
        self.payments = PostgreSQLClient()
        self.inventory = PostgreSQLClient()
        self.config = etcdClient()

        # AP: High availability for scale
        self.feed = DynamoDBClient(consistency='EVENTUAL')
        self.analytics = BigQueryClient()

        # Hybrid: Timeline consistency
        self.cart = RedisClient()  # User's session
        self.cart_backup = PostgreSQLClient()  # Source of truth
```

**Recommendation:** Option C - Mix databases based on workload requirements.

---

## Key Takeaways

1. **CAP is about tradeoffs during partition** - there's no perfect system
2. **P is mandatory in distributed systems** - networks WILL fail
3. **Choose C vs A based on business requirements** - not technical preferences
4. **Hybrid approaches are common** - use different systems for different workloads
5. **Understanding NRW formula** - R + W > N for strong consistency

---

## Real-World CAP Positions

| System | CAP Position | Tradeoff |
|--------|-------------|----------|
| PostgreSQL | CA (becomes CP when replicated) | Single-region, strong consistency |
| etcd | CP | Rejects requests if quorum lost |
| Cassandra | AP (configurable to CP) | Available but may return stale data |
| DynamoDB | Configurable | Choose per-operation |
| Spanner | CP (global) | Strong consistency with latency cost |
| MongoDB | CP (with majority write concern) | Strong consistency, limited availability |
| Redis Cluster | CP | Available only if majority reachable |
| CockroachDB | CP | Strong consistency, scales horizontally |
| Consul | CP | Strong consistency for config |
| Riak KV | AP | Always available, eventual consistency |
