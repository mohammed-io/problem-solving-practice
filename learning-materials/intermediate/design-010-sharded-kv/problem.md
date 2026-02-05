---
name: design-010-sharded-kv
description: Distributed key-value store design
difficulty: Intermediate
category: System Design
level: Staff Engineer
---
# Design 010: Sharded Key-Value Store

---

## Tools & Prerequisites

To design and debug sharded KV stores:

### Distributed Systems Tools

| Tool | Purpose | Quick Usage |
|------|---------|-------------|
| **etcd** | Distributed KV store (Raft) | `etcdctl get key`, `etcdctl put key value` |
| **Consul** | Service discovery + KV | `consul kv get key` |
| **Redis Cluster** | Sharded Redis | `redis-cli -c -p 7000` |
| **Cassandra** | Distributed wide-column | `cqlsh` |
| **DynamoDB-local** | Local DynamoDB testing | `java -Djava.library.path=./DynamoDBLocal_lib -jar DynamoDBLocal.jar` |

### Key Concepts

**Sharding**: Splitting data across multiple servers based on a shard key.

**Replication Factor (RF)**: Number of copies of each data (e.g., RF=3 means 3 copies).

**Quorum**: Minimum nodes required for operation; typically `RF/2 + 1`.

**Partition Key**: Key used to determine which shard owns the data.

**Consistent Hashing**: Hash ring minimizing data movement when topology changes.

**Vector Clock**: Data structure tracking causality between replicas.

**Gossip Protocol**: Peer-to-peer state dissemination for cluster membership.

**Rebalancing**: Moving data between shards when adding/removing nodes.

**Write Path**: Client → Coordinator → Replica → Quorum → Response.

**Read Path**: Client → Coordinator → Replica → Quorum → Response.

---

## Visual: Sharded KV Architecture

### Sharded Architecture Overview

```mermaid
flowchart TB
    subgraph Clients ["Client Layer"]
        C1["Client 1"]
        C2["Client 2"]
        CN["Client N"]
    end

    subgraph Coordinator ["Coordinator Layer"]
        Coord["Request Router<br/>(Load Balancer / Gateway)"]
    end

    subgraph Shards ["Shard Layer"]
        S1["Shard 1<br/>Keys: hash % 4 = 0"]
        S2["Shard 2<br/>Keys: hash % 4 = 1"]
        S3["Shard 3<br/>Keys: hash % 4 = 2"]
        S4["Shard 4<br/>Keys: hash % 4 = 3"]
    end

    subgraph Replicas ["Replica Layer (per shard)"]
        R1["S1 Primary"]
        R1a["S1 Replica A"]
        R1b["S1 Replica B"]
    end

    C1 --> Coord
    C2 --> Coord
    CN --> Coord

    Coord -->|"hash(key) % 4"| S1
    Coord -->|"hash(key) % 4"| S2
    Coord -->|"hash(key) % 4"| S3
    Coord -->|"hash(key) % 4"| S4

    S1 --> R1
    R1 -.-> R1a
    R1 -.-> R1b
```

### Sharding Strategies Comparison

```mermaid
flowchart TB
    subgraph Hash ["Hash-Based Sharding"]
        H1["shard = hash(key) % N"]
        H2["✅ Even distribution"]
        H3["❌ All keys move when N changes"]
        H1 --> H2
        H1 --> H3
    end

    subgraph Range ["Range-Based Sharding"]
        R1["shard = key_range(key)"]
        R2["✅ Range queries efficient"]
        R3["❌ Hot spot if keys skewed"]
        R1 --> R2
        R1 --> R3
    end

    subgraph Consistent ["Consistent Hashing"]
        C1["shard = hash_ring(key)"]
        C2["✅ Minimal data movement"]
        C3["✅ Add/remove nodes smoothly"]
        C1 --> C2
        C1 --> C3
    end

    style Consistent fill:#c8e6c9
    style Hash fill:#fff3e0
    style Range fill:#e1f5fe
```

### Write Path with Quorum

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant Coord as Coordinator
    participant P as Primary
    participant R1 as Replica 1
    participant R2 as Replica 2

    Note over Client,R2: Replication Factor = 3, Quorum = 2

    Client->>Coord: SET key=value

    Coord->>Coord: shard = hash(key) % N

    Coord->>P: Forward SET key=value
    Coord->>R1: Forward SET key=value
    Coord->>R2: Forward SET key=value

    P-->>Coord: ACK (1)
    R1-->>Coord: ACK (2)

    Note over Coord: Quorum reached!

    Coord-->>Client: Success

    R2-->>Coord: ACK (3) - Late, doesn't matter
```

### Read Repair

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant Coord as Coordinator
    participant R1 as Replica 1<br/>(stale)
    participant R2 as Replica 2<br/>(stale)
    participant P as Primary<br/>(fresh)

    Client->>Coord: GET key

    par Parallel reads
        Coord->>R1: GET key
        Coord->>R2: GET key
        Coord->>P: GET key
    end

    R1-->>Coord: value=v1, version=1
    R2-->>Coord: value=v2, version=1
    P-->>Coord: value=v3, version=2

    Note over Coord: Version 2 is latest!

    Coord->>Coord: Return v3 to client

    Coord->>R1: Repair: SET key=v3, version=2
    Coord->>R2: Repair: SET key=v3, version=2

    Note over Coord,R2: Read repair completed
```

### Handling Hot Keys

```mermaid
flowchart TB
    subgraph Problem ["🔴 Hot Key Problem"]
        Hot["Key: popular_user<br/>10,000 req/s"]
        S1["Shard 1<br/>Normal load: 100 req/s"]
        Overwhelmed["Shard 1 now: 10,100 req/s<br/>❌ OVERWHELMED!"]

        Hot --> S1
        S1 --> Overwhelmed
    end

    subgraph Solutions ["✅ Mitigation Strategies"]
        SL["Split hot key<br/>(popular_user → popular_user_1,2,3)"]
        Cache["Local caching<br/>at application layer"]
        Replica["Extra replicas<br/>for hot keys only"]
        Throttle["Rate limiting<br/>protect shard"]

        SL --> Cache
        Cache --> Replica
        Replica --> Throttle
    end

    style Problem fill:#ffcdd2
    style Solutions fill:#c8e6c9
```

### Rebalancing Data

```mermaid
sequenceDiagram
    autonumber
    participant Admin
    participant Cluster
    participant S3 as New Shard 3
    participant S1 as Shard 1
    participant S2 as Shard 2

    Note over Admin,S2: Original: 2 shards, 50% data each

    Admin->>Cluster: Add shard 3

    Cluster->>S3: Initialize new shard

    Cluster->>S1: Move keys to S3<br/>(hash % 3 = 2)
    S1-->>S3: Transfer 1/6 of data

    Cluster->>S2: Move keys to S3<br/>(hash % 3 = 2)
    S2-->>S3: Transfer 1/6 of data

    Note over Cluster: Rebalance complete!<br/>Each shard has 33% of data
```

### CAP Theorem Trade-offs

```mermaid
graph TB
    subgraph CAP ["CAP Theorem for Sharded KV"]
        C["🔵 Consistency<br/>Every read sees latest write"]
        A["🟢 Availability<br/>Every request succeeds"]
        P["🟡 Partition Tolerance<br/>System works during network split"]

        Note1["Pick 2 of 3"]
    end

    subgraph CA ["CA System (Not really distributed)"]
        CA1["✅ Strong consistency"]
        CA2["✅ Always available"]
        CA3["❌ Fails during partition"]
    end

    subgraph CP ["CP System (e.g., HBase, MongoDB)"]
        CP1["✅ Strong consistency"]
        CP2["✅ Tolerates partitions"]
        CP3["❌ May reject writes"]
    end

    subgraph AP ["AP System (e.g., DynamoDB, Cassandra)"]
        AP1["✅ Always available"]
        AP2["✅ Tolerates partitions"]
        AP3["❌ Eventual consistency"]
    end

    style AP fill:#c8e6c9
    style CP fill:#fff3e0
    style CA fill:#ffcdd2
```

### Request Flow

```mermaid
flowchart LR
    subgraph Write ["Write Request Flow"]
        W1["Client: SET k=v"]
        W2["Coordinator<br/>hash(k) → shard"]
        W3["Shard Primary<br/>Write to WAL"]
        W4["Replicas<br/>Async sync"]
        W5["Quorum<br/>Wait for R/W responses"]
        W6["Response<br/>ACK to client"]

        W1 --> W2 --> W3 --> W4 --> W5 --> W6
    end

    subgraph Read ["Read Request Flow"]
        R1["Client: GET k"]
        R2["Coordinator<br/>hash(k) → shard"]
        R3["Any Replica<br/>Read data"]
        R4["Response<br/>Return value"]

        R1 --> R2 --> R3 --> R4
    end

    style Write fill:#e3f2fd
    style Read fill:#f3e5f5
```

### Node Failure Recovery

```mermaid
stateDiagram-v2
    [*] --> Healthy

    Healthy --> Degraded: Node failure detected

    Degraded --> Degraded: Serve from remaining replicas<br/>(RF=3, now 2 available)

    Degraded --> Replacing: Start replacement node

    Replacing --> Bootstrapping: Copy data from replicas

    Bootstrapping --> CatchingUp: Replay WAL

    CatchingUp --> Healthy: Sync complete

    note right of Degraded
        Quorum still possible
        if RF >= 3
    end note
```

---

## The Requirement

Your team needs to build a distributed key-value store:

**Functional requirements:**
- `GET(key)` → value or "not found"
- `SET(key, value)` → success/error
- `DELETE(key)` → success/error

**Non-functional requirements:**
- Scale to 10 billion keys
- Handle 1 million reads/second, 100,000 writes/second
- < 50ms P99 latency for reads
- < 100ms P99 latency for writes
- Highly available (99.99% uptime)
- Eventually consistent (tolerate brief inconsistencies)

**Constraints:**
- Keys are strings (1-256 bytes)
- Values are blobs (up to 1 MB)
- Total data: ~100 TB
- Budget: Limited (can't just throw money at it)

---

## What is Sharding?

Imagine a library with millions of books.

**Unsharded (single server):**
- All books in one building
- One librarian handles all requests
- When building is full, you're stuck

**Sharded (distributed):**
- Books split across multiple buildings
- Each building has its own librarian
- When one building is full, add another
- Each request goes to specific building based on book category

**In database terms:** Sharding splits data across multiple servers based on a shard key.

---

## Questions to Answer

### 1. Data Model

What does the data model look like?

```sql
-- Option 1: Simple table
CREATE TABLE kv (
    key TEXT PRIMARY KEY,
    value BYTEA,
    version BIGINT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);

-- Option 2: With TTL
CREATE TABLE kv (
    key TEXT PRIMARY KEY,
    value BYTEA,
    version BIGINT,
    expires_at TIMESTAMPTZ
);
```

**What about TTL (time-to-live) for automatic expiration?**

### 2. Sharding Strategy

How do you distribute keys across shards?

**Option A: Hash-based sharding**
```
shard = hash(key) % N
```

**Option B: Range-based sharding**
```
shard = find_shard_by_range(key, ranges)
```

**Option C: Consistent hashing**
```
shard = consistent_hash(key, ring)
```

**What are the trade-offs?**

### 3. Replication

How do you handle replication for high availability?

**Option A: Master-slave**
```
Write → Master → Slaves (read-only)
Read  → Slaves
```

**Option B: Multi-master**
```
Write → Any master → Sync to other masters
Read  → Any node
```

**Option C: Raft-based consensus**
```
Write → Leader → Followers (quorum required)
Read  → Leader (strong) or Follower (eventual)
```

### 4. Consistency vs Availability

Which to prioritize?

- **Strong consistency:** Every read sees latest write (CAP theorem: CA, not AP)
- **Eventual consistency:** Reads might be stale but system stays available (CAP: AP)

### 5. Handling Hot Keys

What if one key is very popular?

```
key: "global_config"  → 1 million reads/second
shard: 5              → 200,000 reads/second just for this key!
```

---

## Jargon

| Term | Definition |
|------|------------|
| **Sharding** | Splitting data across multiple servers based on a key |
| **Replication** | Copying data to multiple servers for redundancy |
| **Consistent hashing** | Hashing technique minimizing data movement when adding/removing nodes |
| **Quorum** | Minimum nodes required for operation (e.g., 2 of 3) |
| **Hot key** | Key accessed much more frequently than others (skew) |
| **Split brain** | When network partition causes multiple nodes to think they're leader |
| **Vector clock** | Data structure for tracking causality in distributed systems |
| **Gossip protocol** | Nodes periodically share state with random peers |
| **Rebalancing** | Moving data between shards when adding/removing nodes |
| **TTL (Time To Live)** | Automatic expiration of data after specified time |
| **Write path** | Journey of write from client to durable storage |
| **Read path** | Journey of read from client to returning value |

---

## Your Task

Design the system addressing:

1. **Sharding strategy** (how to distribute keys)

2. **Replication strategy** (how to ensure availability)

3. **Handling node failures** (what happens when shard goes down)

4. **Handling rebalancing** (adding/removing shards)

5. **Handling hot keys** (what about skewed access patterns)

6. **Operational concerns** (monitoring, deployment, capacity planning)

---

**When you have a design, read `step-01.md`**
