# Terminology & Jargon Dictionary

**Technical terms used throughout the problems, explained simply.**

---

## A

| Term | Definition |
|------|------------|
| **ACID** | Atomicity, Consistency, Isolation, Durability - database transaction guarantees |
| **Availability Zone (AZ)** | Data center within a region, isolated from other AZs |
| **Auto-scaling** | Automatically adding/removing resources based on load |
| **Backpressure** | Slowing down input when output can't keep up |
| **Base 64** | Binary-to-text encoding, makes binary data safe for text protocols |

## B

| Term | Definition |
|------|------------|
| **BGP** | Border Gateway Protocol - how routes are announced on the internet |
| **Bind mount** | Mounting a file/directory from host into container |
| **Bloat** | Database tables becoming larger than necessary (dead tuples) |
| **Bottleneck** | The component limiting overall system performance |
| **Buffer** | Temporary storage area for data being moved |

## C

| Term | Definition |
|------|------------|
| **Cache stampede** | Multiple sources refreshing same cached item simultaneously |
| **Cache avalanche** | Large portion of cache expiring at once, overwhelming origin |
| **Cardinality** | Number of unique values in a column (high = many unique values) |
| **CIDR** | Classless Inter-Domain Routing - IP address notation (e.g., 10.0.0.0/16) |
| **Cold start** | Delay before serverless function can handle first request |
| **Connection pool** | Reuse of database connections instead of creating new ones |
| **Consistent hashing** | Hashing that minimizes remapping when nodes are added/removed |
| **Correlation ID** | Unique ID to trace requests across services |
| **CPU bound** | Limited by CPU, not I/O |

## D

| Term | Definition |
|------|------------|
| **Daemon** | Background process that runs continuously |
| **Data race** | Unsynchronized access to shared data in concurrent code |
| **Deadlock** | Two or more processes waiting on each other, none can proceed |
| **Dirty read** | Reading uncommitted data from another transaction |
| **DNS** | Domain Name System - translates names to IPs |
| **Dormant** | Not active but can be activated (e.g., cold standby) |

## E

| Term | Definition |
|------|------------|
| **Egress** | Outbound network traffic |
| **Ephemeral port** | Temporary port assigned by OS for outbound connection |
| **EVICTION** | Forcing a pod/tenant off a node (resource pressure) |
| **Explainer** | In ML, technique to understand model decisions |

## F

| Term | Definition |
|------|------------|
| **Fan-in** | Multiple inputs going to one component |
| **Fan-out** | One output going to multiple components |
| **Fast path** | Optimized code path for common cases |
| **Finalizer** | Code that runs when an object is garbage collected |
| **Firehose** | Stream of all events (vs. filtered/sample) |
| **Forward proxy** | Proxy for outbound traffic |
| **Free list** | Pool of reusable objects to avoid allocation |

## G

| Term | Definition |
|------|------------|
| **Garbage collection** | Automatic memory management |
| **GET** | HTTP method to retrieve data |
| **Goroutine leak** | Goroutines created but never terminated |
| **Graceful degradation** | System continues working at reduced capacity when failing |

## H

| Term | Definition |
|------|------------|
| **Handshake** | Initial negotiation between systems |
| **Head of line blocking** | One slow request blocks subsequent requests |
| **Heap** | Dynamic memory region |
| **Hot partition** | Partition receiving more traffic than others |
| **Hot spot** | Frequently accessed data/resource |

## I

| Term | Definition |
|------|------------|
| **Idempotent** | Same operation can be applied multiple times with same result |
| **Ingress** | Inbound network traffic |
| **Index** | Data structure to speed up queries |
| **IO bound** | Limited by I/O, not CPU |
| **Isolation level** | Transaction concurrency guarantees (read committed, serializable, etc.) |

## J

| Term | Definition |
|------|------------|
| **Jitter** | Random delay added to periodic tasks to avoid synchronization |
| **Journaling** | Writing changes to log before applying to main storage |
| **JSON** | JavaScript Object Notation - data interchange format |
| **JWT** | JSON Web Token - signed token for authentication |

## K

| Term | Definition |
|------|------------|
| **Keepalive** | Message sent to keep connection open |
| **Kernel** | Core of operating system, manages resources |
| **Key space** | Range of possible keys in a data store |
| **Kill switch** | Mechanism to quickly disable a feature |

## L

| Term | Definition |
|------|------------|
| **Lagged replica** | Replica behind primary (replication delay) |
| **Latency** | Time delay between request and response |
| **Leader election** | Process of selecting a coordinator in distributed system |
| **Lease** | Time-limited lock |
| **Liveness** | Property that something good eventually happens |
| **Lock** | Mechanism to prevent concurrent access |

## M

| Term | Definition |
|------|------------|
| **Materialized view** | Pre-computed query result stored as table |
| **Memoization** | Caching function results |
| **Mitigation** | Action to reduce impact (not fix root cause) |
| **Monitor** | Process that watches for issues |
| **MTTR** | Mean Time To Recovery - how long to fix incidents |
| **MTTD** | Mean Time To Detect - how long to notice issues |
| **MVCC** | Multi-Version Concurrency Control - how Postgres handles concurrent transactions |

## N

| Term | Definition |
|------|------------|
| **N+1 query** | One query to get N items, then N queries to get related data |
| **Namespace** | Isolated scope for resources |
| **Network partition** | Network failure preventing communication between nodes |
| **Node** | Single machine in a cluster |
| **Nonce** | Number used once - for uniqueness/replay prevention |

## O

| Term | Definition |
|------|------------|
| **Object storage** | S3-style storage (unlike file systems, no directories) |
| **On-call** | Being responsible for responding to incidents |
| **OOM** | Out Of Memory - killed for using too much memory |
| **Orphan** | Resource without owner/parent |
| **Overflow** | Value too large for its data type |

## P

| Term | Definition |
|------|------------|
| **Page** | Fixed-size block of memory/disk storage |
| **Page cache** | OS cache for frequently accessed disk data |
| **PagerDuty** | On-call management service (also used generically) |
| **Partition** | Subset of data, or network failure |
| **P99** | 99th percentile - value at 99% of measurements |
| **P95** | 95th percentile - value at 95% of measurements |
| **Phantom read** | Rows appear/disappear across re-reads in a transaction |
| **Pinning** | Keeping data in memory/cache |
| **Pool** | Collection of reusable resources |
| **Postmortem** | Document written after incident analyzing what happened |
| **Pressure** | Resource contention (CPU pressure, memory pressure) |
| **Primary key** | Unique identifier for database row |
| **Probe** | Health check (liveness, readiness, startup) |
| **Process** | Running instance of a program |

## Q

| Term | Definition |
|------|------------|
| **Quorum** | Minimum number of votes needed for decision |
| **Query plan** | How database executes a query (explain output) |
| **Queue** | FIFO data structure for work items |
| **Queuing theory** | Math for analyzing queue behavior |

## R

| Term | Definition |
|------|------------|
| **Race condition** | Output depends on timing of uncontrollable events |
| **Range scan** | Querying sequential keys |
| **Rate limiting** | Restricting number of requests per time period |
| **Read replica** | Database copy that serves only read queries |
| **Rebalance** | Redistributing data across nodes |
| **Recovery** | Process of restoring system to working state |
| **Redundancy** | Duplicated components for reliability |
| **Replica** | Copy of data/service |
| **Replication lag** | Delay between primary and replica update |
| **Request rate** | Requests per second |
| **Retries** | Attempting failed operation again |
| **Reverse proxy** | Proxy for inbound traffic |
| **Rollback** | Reverting to previous version |
| **Rolling deploy** | Updating instances one at a time |
| **Round-robin** | Distributing requests sequentially across targets |
| **Row lock** | Lock on specific database row |

## S

| Term | Definition |
|------|------------|
| **Scale up** | Adding resources to single machine |
| **Scale out** | Adding more machines |
| **Scatter-gather** | Send to many, collect responses |
| **Schema** | Database structure definition |
| **Schema migration** | Changing database structure |
| **Secondary index** | Additional index beyond primary key |
| **Segmentation fault** | Program accessing invalid memory |
| **Semaphore** | Variable controlling concurrent access |
| **Serialization** | Converting object to byte stream |
| **Shard** | Horizontal partition of data |
| **Sidecar** | Helper container running alongside main container |
| **SLA** | Service Level Agreement - promised metrics |
| **SLO** | Service Level Objective - target metric values |
| **Snapshot** | Point-in-time copy of data/state |
| **Socket** | Endpoint for network communication |
| **Split-brain** | Two parts of system thinking they're in charge |
| **SPOF** | Single Point Of Failure |
| **Stack trace** | Sequence of function calls showing execution path |
| **Stateful** | Component that remembers data across requests |
| **Stateless** | Component that doesn't remember between requests |
| **Stop-the-world** | Pausing all execution for GC/cleanup |
| **Subnet** | Logical subdivision of network |
| **Synchronous** | Operations that wait for completion |
| **Syscall** | Request from program to OS kernel |

## T

| Term | Definition |
|------|------------|
| **TCP** | Transmission Control Protocol - reliable data delivery |
| **Throughput** | Data processed per time unit |
| **Throttle** | Intentionally limit rate |
| **Thundering herd** | Many sources overwhelming system simultaneously |
| **Timeout** | Time limit for operation |
| **TLS** | Transport Layer Security - encrypted communication |
| **Topology** | Arrangement of nodes and connections |
| **Trace** | Record of request's path through system |
| **Transaction** | Group of operations treated as atomic unit |
| **TTL** | Time To Live - expiration time |

## V

| Term | Definition |
|------|------------|
| **VACUUM** | PostgreSQL operation to reclaim space from dead tuples |
| **Vertical scaling** | Adding resources to single machine (scale up) |
| **Virtualization** | Running multiple virtual machines on one physical |
| **VLAN** | Virtual LAN - logical network segmentation |
| **Volume** | Persistent storage in container orchestration |
| **VPC** | Virtual Private Cloud - isolated network in cloud |

## W

| Term | Definition |
|------|------------|
| **WAL** | Write-Ahead Log - PostgreSQL's journal for crash recovery |
| **Warm start** | Restarting with cached data |
| **Warm up** | Period before system can handle full load |
| **Watcher** | Process that monitors for changes |
| **Watermark** | Threshold for resource usage |
| **Worker pool** | Set of reusable worker threads/processes |

---

## Common Patterns

### Database Index Types

| Type | Use Case | Example |
|------|----------|---------|
| **B-tree** | Equality and range queries | `WHERE id = 5`, `WHERE created_at > NOW()` |
| **Hash** | Equality only | `WHERE user_id = 123` |
| **GIN** | Array/full-text search | `WHERE tags @> ARRAY['python']` |
| **BRIN** | Very large tables with natural ordering | Time-series data |

### CAP Theorem

Pick two:
- **C**onsistency - All nodes see same data simultaneously
- **A**vailability - Every request gets a response
- **P**artition tolerance - System works despite network failure

### ACID vs BASE

| ACID (Traditional) | BASE (NoSQL) |
|--------------------|--------------|
| Atomic | Basically Available |
| Consistent | Soft state |
| Isolated | Eventually consistent |
| Durable | - |

---

**Encountered a term not listed here? Look it up and add it for the next person!**
