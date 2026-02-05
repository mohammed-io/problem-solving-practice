---
name: design-102-cap-tradeoffs
description: CAP Theorem Tradeoffs in...
difficulty: Advanced
category: Design / Distributed Systems / CAP Theorem
level: Principal Engineer
---
# Design 102: CAP Theorem Tradeoffs in Real Systems

---

## Tools & Prerequisites

To analyze CAP theorem tradeoffs:

### Distributed System Analysis Tools

| Tool | Purpose | Quick Usage |
|------|---------|-------------|
| **Jepsen** | Distributed system testing | `lein run test --nemesis generic |
| **Chaos Mesh** | Chaos engineering in K8s | `chaosctl apply chaos.yaml` |
| **Ping/latency tests** | Network partition simulation | `ping -i 0.1 -c 100 host` |
| **etcdctl** | Check quorum status | `etcdctl endpoint status --write-out=table` |
| **consul kv get** | Check consistency | `consul kv get -consistent key` |
| **redis-cli --latency** | Measure latency | `redis-cli --latency-history` |
| **cassandra-stress** | Test Cassandra consistency | `cassandra-stress write n=100000` |

### Key Commands

```bash
# Check Cassandra consistency level
nodetool describecluster
cqlsh -e "SELECT CONSISTENCY;"

# Monitor etcd health and quorum
etcdctl endpoint health --cluster
etcdctl member list

# Test Redis Sentinel failover
redis-cli -p 26379 sentinel masters
redis-cli -p 26379 sentinels mymaster

# Check ZooKeeper quorum
echo "stat" | nc localhost 2181
zkCli.sh -server localhost:2181 get /zookeeper/config

# Simulate network partition with iptables
iptables -A INPUT -s <peer_ip> -j DROP
iptables -A OUTPUT -d <peer_ip> -j DROP

# Check DynamoDB table status
aws dynamodb describe-table --table-name mytable

# Test CockroachDB range splits
cockroach sql --insecure -e "SHOW REGIONS FROM TABLE mytable;"

# Monitor MongoDB replica set
rs.status()
rs.isMaster()

# Check Consul consistency
consul info -raft
curl http://localhost:8500/v1/status/leader

# Test MongoDB write concern
mongo --eval "db.myCollection.insert({data: 'test'}, {writeConcern: {w: 'majority'}})"
```

### Key Concepts

**CAP Theorem**: In a distributed system, you can only have 2 of 3 properties: Consistency, Availability, Partition Tolerance.

**Consistency (C)**: All nodes see same data simultaneously; linearizable reads.

**Availability (A)**: Every request receives response (success/failure), without guarantee of most recent data.

**Partition Tolerance (P)**: System continues operating despite network partitions between nodes.

**CA System**: RDBMS with single node (MySQL, PostgreSQL); fails on partition.

**CP System**: Prioritizes consistency over availability (HBase, MongoDB, Redis Cluster, etcd, ZooKeeper).

**AP System**: Prioritizes availability over consistency (Cassandra, DynamoDB, CouchDB, CosmosDB).

**Network Partition**: Communication failure between nodes; P is mandatory in distributed systems.

**Quorum**: Minimum nodes required for operation (majority: N/2 + 1).

**Write Concern**: How many nodes must acknowledge write (w=1, w=quorum, w=all).

**Read Concern**: How many nodes queried for read (r=1, r=quorum, r=all).

**Eventual Consistency**: System guarantees convergence to consistent state eventually.

**Strong Consistency**: Linearizable; reads return most recent write.

**Timeline Consistency**: Users see their own writes; others may see stale data.

**Read Repair**: Background process reconciling divergent replicas.

**Hinted Handoff**: Temporary storage for writes during node failure.

**Vector Clock**: Logical clock for tracking causal relationships in AP systems.

**Gossip Protocol**: Peer-to-peer communication for state dissemination.

**Last-Write-Wins**: Conflict resolution using timestamps (LWW).

**RAFT**: Consensus algorithm for CP systems (etcd, CockroachDB, Consul).

**Paxos**: Classic consensus algorithm (Google Spanner).

**NRW**: Replication factor N, reads R, writes W; R + W > N for consistency.

---

## The Situation

You're a Principal Architect at a rapidly growing startup. You need to choose databases for three different workloads, each with different CAP requirements:

```
Workload 1: Payment Processing
- Requirement: No double-spending, must be accurate
- Scale: 10,000 transactions/second
- Tolerance: Downtime acceptable, data errors NOT acceptable

Workload 2: Social Media Feed
- Requirement: Always fast, occasional duplicates OK
- Scale: 1M requests/second
- Tolerance: Stale data acceptable, downtime NOT acceptable

Workload 3: Shopping Cart
- Requirement: User sees their own changes
- Scale: 100,000 carts/second
- Tolerance: Temporary inconsistency acceptable
```

---

## The Challenge

**Your team is debating:**

```
Option A: Use DynamoDB for everything (AP + configurable consistency)
Option B: Use PostgreSQL with replication (CA, becomes CP when partitioned)
Option C: Mix: PostgreSQL for payments, DynamoDB for feed, Redis for carts
Option D: Build on CockroachDB (CP, scales globally)
```

**Business constraints:**
- Engineering team knows PostgreSQL
- Need to deploy in 3 regions (US, EU, Asia)
- Must survive single-region failure
- Compliance requires audit trails for payments

---

## Visual: CAP Theorem Triangle

### The CAP Triangle

```mermaid
flowchart TB
    subgraph CAP [CAP Theorem Triangle]
        C["Consistency (C)
        All nodes see same data
        Linearizable reads
        No stale data"]
        A["Availability (A)
        Every request gets response
        No timeouts
        Always accessible"]
        P["Partition Tolerance (P)
        Survives network failures
        Handles message loss
        Works despite partitions"]

        C --- A
        A --- P
        P --- C

        CA_Label["CA: Single-node RDBMS
        MySQL, PostgreSQL
        Fails on partition"]
        AP_Label["AP: Always available
        Cassandra, DynamoDB
        Stale data possible"]
        CP_Label["CP: Consistent or down
        etcd, ZooKeeper, HBase
        Rejects requests if unsure"]

        C -.-> CA_Label
        A -.-> CA_Label
        A -.-> AP_Label
        P -.-> AP_Label
        P -.-> CP_Label
        C -.-> CP_Label
    end

    classDef ca fill:#e3f2fd,stroke:#1976d2
    classDef ap fill:#fff3e0,stroke:#f57c00
    classDef cp fill:#f3e5f5,stroke:#7b1fa2

    class CA_Label ca
    class AP_Label ap
    class CP_Label cp
```

### Real Systems CAP Positioning

```mermaid
flowchart LR
    subgraph Systems ["Real-World Systems on CAP Spectrum"]
        direction TB
        CP["CP Systems
        ─────────────
        etcd (RAFT)
        ZooKeeper (ZAB)
        HBase (Google Bigtable)
        MongoDB (majority)
        Redis Cluster
        CockroachDB
        Consul
        ElasticSearch (by default)"]

        AP["AP Systems
        ─────────────
        Cassandra (eventual)
        DynamoDB (eventual)
        CouchDB
        CosmosDB (eventual)
        Riak KV
        Cassandra (QUORUM=CP)
        DynamoDB (consistent reads)"]

        CA["CA Systems
        ─────────────
        Single-node MySQL
        Single-node PostgreSQL
        Single-node Redis
        (Not distributed!)"]

        HYBRID["Hybrid/Configurable
        ────────────────────
        DynamoDB (choose R+W)
        Cassandra (CL level)
        Spanner (TrueTime)
        FoundationDB
        FaunaDB
        YugabyteDB"]
    end

    CP --- HYBRID
    HYBRID --- AP
    CA -.->|"becomes CP
    when partitioned"| HYBRID

    classDef cp fill:#f3e5f5,stroke:#7b1fa2
    classDef ap fill:#fff3e0,stroke:#f57c00
    classDef ca fill:#e3f2fd,stroke:#1976d2
    classDef hybrid fill:#e8f5e9,stroke:#388e3c

    class CP cp
    class AP ap
    class CA ca
    class HYBRID hybrid
```

---

## Real-World Case Studies

### Case 1: Amazon DynamoDB - AP with Configurable Consistency

**Based on:** Amazon's internal Dynamo paper, later productized as DynamoDB

```mermaid
flowchart TB
    subgraph DynamoDB ["DynamoDB: AP with Tunable Consistency"]
        Request["Client Request"]

        Write["Write Path:
        W = 1 (Fast, potentially stale)
        W = 2 (Better durability)
        W = QUORUM (Consistent, slower)"]

        Read["Read Path:
        R = 1 (Fast, stale possible)
        R = 2 (More recent)
        R = QUORUM (Consistent, slower)"]

        Storage["Storage:
        N = 3 replicas per item
        Leader-based writes
        Async replication to followers"]

        Consistency["Consistency Levels:
        • EVENTUAL (default)
        • STRONG (read-after-write)
        • ATOMIC (transactional)
        • TIMELINE (session-level)"]
    end

    Request --> Write
    Request --> Read
    Write --> Storage
    Read --> Storage
    Storage --> Consistency

    classDef strong fill:#4caf50,stroke:#2e7d32,color:#fff
    classDef eventual fill:#ffc107,stroke:#f57c00

    class Consistency strong
```

**Amazon's Choice:** AP with configurable consistency
- Default: Eventual consistency for low latency
- Option: Strong reads when needed (payment operations)
- Tradeoff: 50ms latency difference between eventual/strong reads

---

### Case 2: Google Spanner - "False" CP with TrueTime

**Based on:** Google Spanner, the database behind Google Ads and Gmail

```mermaid
flowchart TB
    subgraph Spanner ["Spanner: CP via TrueTime"]
        TT["TrueTime API
        ─────────────────
        tt.now(): [earliest, latest]
        Uncertainty: ε (~10ms)
        Uses atomic clocks + GPS"]

        Commit["External Consistency
        ──────────────────────
        Commit waits until
        tt.now().earliest > ts + ε
        Guarantees global ordering"]

        Regions["Multi-Region
        ─────────────
        3 replicas, different zones
        2 replicas must commit
        Reads use timestamp"]

        Result["Result: True CP
        ────────────────────
        Strong consistency
        Globally distributed
        Latency: 50-100ms
        Cost: VERY HIGH $$"]
    end

    TT --> Commit
    Commit --> Regions
    Regions --> Result

    classDef good fill:#4caf50,stroke:#2e7d32,color:#fff
    classDef warn fill:#ffc107,stroke:#f57c00

    class TT,Commit,Result good
    class Regions warn
```

**Google's Choice:** CP with TrueTime
- Sacrifices some latency for consistency
- Can serve reads without round-trip to leader
- Uses atomic clocks + GPS for global time synchronization

---

### Case 3: Cassandra at Netflix - AP with Tunable CL

**Based on:** Netflix's migration from Oracle to Cassandra (2010-2013)

```mermaid
flowchart TB
    subgraph NetflixCassandra ["Netflix: AP with Multiple CLs"]
        Profile["User Profile Data
        ───────────────────
        CL = QUORUM (2 of 3)
        Reason: Privacy critical
        Tradeoff: Acceptable latency"]

        Viewing["Viewing History
        ─────────────────
        CL = ONE (1 of 3)
        Reason: High scale
        Tradeoff: Temporary gaps OK"]

        Bookmark["Bookmarks/Ratings
        ──────────────────────
        CL = LOCAL_QUORUM
        Reason: User timeline consistency
        Tradeoff: Regional availability"]

        Catalog["Catalog Metadata
        ──────────────────────
        CL = QUORUM + read_repair
        Reason: Business critical
        Tradeoff: Background repair"]
    end

    classDef strict fill:#4caf50,stroke:#2e7d32,color:#fff
    classDef loose fill:#fff3e0,stroke:#f57c00
    classDef medium fill:#e8f5e9,stroke:#388e3c

    class Profile,Catalog strict
    class Viewing loose
    class Bookmark medium
```

**Netflix's Choice:** AP with per-operation CL
- Different consistency per use case
- Tunable tradeoff per query
- Global distribution for streaming

---

### Case 4: CockroachDB - CP with Geo-Partitioning

**Based on:** CockroachDB, inspired by Google Spanner

```mermaid
flowchart TB
    subgraph CRDB ["CockroachDB: CP with RAFT"]
        RAFT["RAFT Consensus
        ─────────────
        Range-based replication
        Leader processes writes
        Followers replicate
        Auto-rebalancing"]

        Geo["Geo-Partitioning
        ──────────────────
        database: region 'us-east'
        table: region 'eu-west'
        Data lives where accessed"]

        SQL["SQL Layer
        ─────────
        Distributed transactions
        Strong isolation (serializable)
        Online schema changes"]

        Result["Result: Pure CP
        ───────────────────
        Linearizable consistency
        Survives 1 node failure
        Rejects requests if quorum lost
        Latency: 20-50ms (same region)"]
    end

    RAFT --> Geo
    Geo --> SQL
    SQL --> Result

    classDef good fill:#4caf50,stroke:#2e7d32,color:#fff
    classDef cost fill:#ff9800,stroke:#e65100

    class Result good
```

---

### Case 5: MongoDB - CP with Configurable Write Concern

```mermaid
flowchart LR
    subgraph Mongo ["MongoDB: CP Configurable"]
        W1["w=1 (Acknowledged)<br/>Fast: ~5ms<br/>Risk: Data loss on fail<br/>Use: Caches, logs"]

        Wmaj["w='majority' (Default)<br/>Medium: ~20ms<br/>Durable: Most replicas<br/>Use: Most data"]

        Wall["w=&lt;number&gt; (Custom)<br/>Flexible: N/2 + 1<br/>Control: Explicit count<br/>Use: Special cases"]

        R1["readPreference='primary'<br/>Strong: Always from leader<br/>Latency: Higher<br/>Use: Critical data"]

        R2["readPreference='secondary'<br/>Eventual: From followers<br/>Latency: Lower<br/>Use: Analytics"]
    end

    W1 --> Wmaj --> Wall
    R1 --> R2

    classDef fast fill:#fff3e0,stroke:#f57c00
    classDef safe fill:#e8f5e9,stroke:#388e3c
    classDef middle fill:#e3f2fd,stroke:#1976d2

    class W1,R2 fast
    class Wmaj,R1 safe
    class Wall middle
```

---

## Partition Scenarios

### What Happens During Network Partition?

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant Node1 as Node 1 (Leader)
    participant Node2 as Node 2 (Follower)
    participant Network as Network Partition

    Client->>Node1: Write(key=value)
    Node1->>Node2: Replicate to follower

    Note over Network: PARTITION STARTS

    Node1-xNode2: Connection lost

    Client->>Node1: Write(key=value2)

    alt CP System (etcd, MongoDB, HBase)
        Node1->>Node1: Check quorum
        Node1->>Node1: Only 1 of 3 nodes
        Node1-->>Client: Error: Not enough replicas
        Note over Node1: System UNAVAILABLE
    else AP System (Cassandra, DynamoDB)
        Node1->>Node1: Write anyway
        Node1-->>Client: Success (hinted handoff)
        Note over Node1: Returns stale data
    end

    Note over Network: PARTITION ENDS

    Node1->>Node2: Connection restored
    Node1->>Node2: Sync missed writes
    Node2->>Node2: Read repair / merge
```

### Consistency vs Availability Matrix

```mermaid
graph TB
    subgraph Matrix ["CP vs AP Decision Matrix"]
        direction TB

        CP0["CP: Reject writes
        ──────────────────
        etcd, ZooKeeper
        Consistent > Available
        Return errors"]

        CP1["CP: Queue writes
        ──────────────────
        Kafka, Pulsar
        Buffer during partition
        Degrade gracefully"]

        CP2["CP: Single leader
        ──────────────────
        MongoDB, CockroachDB
        Only leader accepts writes
        Followers error"]

        AP0["AP: Accept everywhere
        ──────────────────────
        Cassandra, DynamoDB
        Last-write-wins
        Merge later"]

        AP1["AP: Timestamp ordering
        ─────────────────────────
        Riak, CouchDB
        Vector clocks
        Causal consistency"]

        AP2["AP: CRDTs
        ───────────────
        AntidoteDB
        Conflict-free types
        Auto-merge"]
    end

    CP0 --> CP1 --> CP2
    AP0 --> AP1 --> AP2

    classDef cp fill:#f3e5f5,stroke:#7b1fa2
    classDef ap fill:#fff3e0,stroke:#f57c00

    class CP0,CP1,CP2 cp
    class AP0,AP1,AP2 ap
```

---

## The NRW Formula

**For consistency: R + W > N**

Where:
- **N** = Replication factor (total replicas)
- **R** = Number of nodes read
- **W** = Number of nodes written

```mermaid
flowchart TB
    subgraph NRW ["NRW Consistency Calculator"]
        N["N = 3 (3 replicas total)

        Options:"]

        W1["W=2, R=2:
        2 + 2 > 3 ✓ Consistent
        Latency: Medium"]

        W2["W=3, R=1:
        3 + 1 > 3 ✓ Consistent
        Latency: High write, fast read"]

        W3["W=1, R=3:
        1 + 3 > 3 ✓ Consistent
        Latency: Fast write, slow read"]

        W4["W=1, R=1:
        1 + 1 < 3 ✗ Eventual
        Latency: Fastest"]
    end

    N --> W1
    N --> W2
    N --> W3
    N --> W4

    classDef good fill:#4caf50,stroke:#2e7d32,color:#fff
    classDef bad fill:#ffc107,stroke:#f57c00

    class W1,W2,W3 good
    class W4 bad
```

---

## Questions

1. **For the payment processing workload, which CAP choice and why?**

2. **For the social media feed, is AP the right choice? What are the tradeoffs?**

3. **How does DynamoDB achieve both AP and CP-like behavior?**

4. **Why is Google Spanner considered CP despite global distribution?**

5. **As a Principal Engineer, design a multi-database architecture for all three workloads with clear CAP justifications.**

---

**When you've thought about it, read `step-01.md`**
