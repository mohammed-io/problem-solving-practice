# Step 01: Understanding CAP Theorem

---

## The CAP Theorem

In a distributed system, you can only have **2 out of 3** properties:

```
┌─────────────────────────────────────┐
│                                     │
│   Consistency  ──────  Availability │
│          \           /              │
│           \         /               │
│            \       /                │
│         Partition Tolerance          │
│                                     │
└─────────────────────────────────────┘
```

**Pick any two... but Partition Tolerance is mandatory in distributed systems.**

---

## The Three Properties

### Consistency (C)
Every read receives the most recent write **or an error**.

```
Node A writes X = 1
Node B reads X → gets 1 (not 0)
All nodes agree on data value
```

### Availability (A)
Every request receives a **response** (not an error), without guarantee of most recent data.

```
Node A is down
Client requests data → Gets response from Node B
(Maybe stale, but always responds)
```

### Partition Tolerance (P)
System continues operating despite network partitions between nodes.

```
Network partition isolates Node A
System still processes requests
Using remaining nodes
```

---

## The Reality: P is Mandatory

In distributed systems, **network partitions happen**. You can't opt out.

```
Real-world partition causes:
- Network cable cut
- Switch failure
- AWS region isolation
- DNS issues
- Firewall misconfiguration

Result: You must choose between C and A during partition
```

---

## CA Systems (Theoretical)

Single-node databases like MySQL, PostgreSQL:

```go
// Single-node PostgreSQL - CA system
type CASystem struct {
    db *sql.DB
}

func (s *CASystem) Write(ctx context.Context, data string) error {
    // Single node, always consistent
    _, err := s.db.ExecContext(ctx, "INSERT INTO data (value) VALUES ($1)", data)
    return err
}

// Problem: If this node fails, system is DOWN
// Not partition tolerant
```

When network fails (server can't be reached): System is **DOWN**.

---

## CP Systems: Choose Consistency

Examples: etcd, ZooKeeper, HBase, MongoDB (majority)

```go
// etcd - CP system
type CPSystem struct {
    client *clientv3.Client
}

func (s *CPSystem) Write(ctx context.Context, key, value string) error {
    // Requires quorum to write
    // If partition prevents quorum: FAIL
    resp, err := s.client.Put(ctx, key, value)
    if err != nil {
        return fmt.Errorf("quorum not reached: %w", err)
    }

    // Write succeeded only if majority acknowledged
    _ = resp.Header.Revision
    return nil
}

// During partition: If node can't reach quorum
// Returns error: "context deadline exceeded" or "quorum not reached"
// System: UNAVAILABLE for writes
```

**Tradeoff:** Reject writes rather than risk inconsistency.

---

## AP Systems: Choose Availability

Examples: Cassandra, DynamoDB, CouchDB

```go
// Cassandra - AP system
type APSystem struct {
    session *gocql.Session
}

func (s *APSystem) Write(ctx context.Context, key, value string) error {
    // Write with ONE consistency (fast, available)
    // Even if partitioned, accepts writes
    err := s.session.Query(`
        INSERT INTO data (key, value)
        VALUES (?, ?)
    `, key, value).Consistency(gocql.One).Exec()

    return err
    // During partition: Still accepts writes
    // Reconciles later when partition heals
}

func (s *APSystem) Read(ctx context.Context, key string) (string, error) {
    // Read might return stale data
    var value string
    err := s.session.Query(`
        SELECT value FROM data WHERE key = ?
    `, key).Consistency(gocql.One).Scan(&value)

    return value, err
    // System: AVAILABLE with potentially stale data
}
```

**Tradeoff:** Accept writes with risk of conflicts/reconciliation later.

---

## Quick Check

Before moving on, make sure you understand:

1. What are the 3 CAP properties? (Consistency, Availability, Partition Tolerance)
2. Why is P mandatory? (Network partitions happen in distributed systems)
3. What happens in CP systems during partition? (Reject writes, become unavailable)
4. What happens in AP systems during partition? (Accept writes, risk inconsistency)
5. Can you have all 3? (No, pick 2, and P is required)

---

**Ready to see CAP in real systems? Read `step-02.md`**
