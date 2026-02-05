---
name: incident-105-leader-election
description: Leader Election Gone Wrong
difficulty: Advanced
category: Distributed Systems / Consensus
level: Principal Engineer
---
# Incident 105: Leader Election Gone Wrong

---

## Tools & Prerequisites

To debug leader election issues:

### Distributed Coordination Tools

| Tool | Purpose | Quick Usage |
|------|---------|-------------|
| **etcdctl** | etcd key-value store (Raft) | `etcdctl member list`, `etcdctl get /leader` |
| **ZooKeeper CLI** | ZK consensus | `zkCli.sh ls /election` |
| **Consul** | Service discovery + KV | `consul kv get leader` |
| **redis** | For distributed locks | `SET lock:leader <value> NX PX 30000` |

### Key Concepts

**Quorum**: Majority of nodes (N/2 + 1) required for valid decisions.

**Term (Raft)**: Monotonically increasing election number; higher term wins.

**Lease**: Time-bounded leadership; must renew or expires.

**Fencing Token**: Unique token that changes; old leader can't operate.

**Bully Algorithm**: Highest-ID node declares victory; vulnerable to split brain.

---

## Visual: Leader Election Issues

### The Bully Algorithm Problem

```mermaid
flowchart TB
    subgraph BeforePartition ["Normal: All Connected"]
        All["Nodes [1,2,3,4,5]"]
        Leader5["Node 5 (highest ID) = Leader"]
        All --> Leader5
    end

    subgraph NetworkPartition ["Network Partition"]
        Part1["Partition 1: Nodes [1,2]"]
        Part2["Partition 2: Nodes [3,4,5]"]
    end

    subgraph AfterPartition ["Split Brain!"]
        Leader2["Node 2 declares leader<br/>(highest in {1,2})"]
        Leader5_2["Node 5 declares leader<br/>(highest in {3,4,5})"]
        Conflict["🚨 Two leaders! No quorum check!"]
    end

    BeforePartition --> NetworkPartition --> AfterPartition
    Leader2 --> Conflict
    Leader5_2 --> Conflict

    style Leader2,Leader5_2,Conflict fill:#dc3545,color:#fff
```

### Split Brain Timeline

```mermaid
sequenceDiagram
    autonumber
    participant N1 as Node 1
    participant N2 as Node 2
    participant N5 as Node 5
    participant Network

    Note over N1,N5: All connected, Node 5 is leader

    Note over N1,N2: Can't reach Node 5
    Note over N5: Can't reach Nodes 1,2

    N1->>N1: No heartbeat from leader!
    N2->>N1: Request votes
    N1->>N2: Vote for Node 2 (it has higher ID)
    N2->>N2: I become leader! (Term 5)

    N5->>N5: No heartbeat from 1,2
    N5->>N5: I still have highest ID, still leader (Term 5)

    Note over N2,N5: 🚨 Two leaders, same term!
```

### Raft-Style Election (Correct)

```mermaid
flowchart TB
    subgraph RaftElection ["✅ Raft: Quorum Required"]
        Nodes["Nodes [1,2,3,4,5]"]
        Quorum["Need 3 of 5 votes"]

        N1["Node 1: Gets 1 vote (itself)"]
        N2["Node 2: Gets 1 vote (itself)"]
        N3["Node 3: Gets 5 votes → LEADER"]

        Nodes --> Quorum
        Quorum --> N3
    end

    subgraph Partition ["During Partition"]
        P1["Partition {1,2}: 2 votes<br/>No quorum!"]
        P2["Partition {3,4,5}: 3 votes<br/>Quorum!"]
        Result["Only {3,4,5} elects leader"]
    end

    classDef good fill:#4caf50,stroke:#2e7d32,color:#fff

    class RaftElection,Nodes,Quorum,N3,Result good
```

### Fencing Token Solution

```mermaid
sequenceDiagram
    autonumber
    participant Old as Old Leader
    participant Storage as Distributed Storage
    participant New as New Leader
    participant Client as Client

    Old->>Storage: Write with token=100
    Storage-->>Old: Success

    Note over Old: Network partition

    New->>Storage: Elect new leader, token=101
    Storage-->>New: You are leader

    Old->>Storage: Write with token=100
    Storage-->>Old: ❌ REJECTED! Token 100 expired
    Note over Old: Fenced out!

    Client->>New: Write request
    New->>Storage: Write with token=101
    Storage-->>New: ✅ Success
```

### Lease-Based Leadership

```mermaid
stateDiagram-v2
    [*] --> Candidate

    Candidate --> Leader: Won election

    Leader --> Leader: Renew lease<br/>(every 5s)

    Leader --> Follower: Lease expired<br/>Network partition?

    Follower --> Candidate: Start new election

    note right of Leader
        Leadership is time-bounded
        Must renew or lose power
    end note
```

## The Situation

Your cluster uses a custom leader election algorithm (not Raft, not Zab):

```go
// "Bully" style leader election
type Node struct {
    id       int
    peers    []int
    isLeader bool
    leaderID int
}

func (n *Node) ElectLeader() {
    // If I have highest ID, I become leader
    for _, peerID := range n.peers {
        if peerID > n.id {
            // Someone has higher ID, wait for them
            return
        }
    }
    // I have highest ID - I'm leader!
    n.isLeader = true
    n.leaderID = n.id
    announceLeadership()
}
```

---

## The Incident Report

```
Time: During network partition

Issue: Multiple leaders elected, split brain, conflicting writes
Impact: Data corruption, conflicting records
Severity: P0 (data loss)

Scenario:
- Cluster: Nodes [1, 2, 3, 4, 5]
- Partition: {1, 2} isolated from {3, 4, 5}
- Node 2 becomes leader for partition {1, 2}
- Node 5 becomes leader for partition {3, 4, 5}
- Both accept writes → merge conflict!
```

---

## What is Leader Election?

**Goal:** In a distributed system, ensure exactly one leader makes decisions.

**Why needed:**
- Prevent split brain (multiple leaders)
- Coordination point for decisions
- Serialize operations

**Common algorithms:**
- **Bully:** Highest ID node becomes leader
- **Raft:** Vote-based with quorum
- **Paxos:** Precursor to Raft
- **Zab:** ZooKeeper's consensus

---

## What is Split Brain?

Imagine a country with two governments claiming to be legitimate.

**Both pass laws, both collect taxes, citizens confused.**

**In systems:**
- Two leaders both think they're in charge
- Both accept writes
- When partition heals: conflicting data!

```
Partition 1:  [Leader 2] accepts writes A, B, C
Partition 2:  [Leader 5] accepts writes X, Y, Z

After heal:  Which writes are valid?
```

---

## The Problems

### Problem 1: No Quorum

Your bully algorithm doesn't require majority:

```
Nodes [1,2,3,4,5]:
- Node 2 sees {1, 2} → 2 out of 5 nodes
- Still becomes leader!
- Should need 3 out of 5 (majority)
```

### Problem 2: Network Partitions

```
Initial:   [1-2-3-4-5] connected
Partition: [1-2] | [3-4-5]

Leader election in each partition:
- [1-2]: Node 2 becomes leader
- [3-4-5]: Node 5 becomes leader

Both think they're legitimate! Split brain!
```

### Problem 3: No Lease

Even after partition heals, both leaders may remain:

```
Node 2: "I was elected first, I'm still leader"
Node 5: "I was elected in my partition, I'm still leader"
```

---

## Jargon

| Term | Definition |
|------|------------|
| **Leader election** | Process of selecting single coordinator in distributed system |
| **Split brain** | Multiple nodes think they're leader simultaneously |
| **Quorum** | Majority of nodes (N/2 + 1) required for decisions |
| **Term** | Logical clock incrementing on each election; higher term wins |
| **Lease** | Time-bounded leadership; must be renewed or expires |
| **Bully algorithm** | Highest-ID node becomes leader; no quorum required |
| **Fencing** | Preventing old leader from making changes (e.g., via token) |
| **Epoch** | Period of time during which a leader is valid |

---

## Questions

1. **Why is quorum necessary for leader election?** (Prevents minority partition leader)

2. **How does Raft prevent split brain?** (Term numbers + quorum)

3. **What's the role of fencing tokens?** (Preventing old leaders)

4. **How do leader leases help?** (Time-bounded authority)

5. **As a Principal Engineer, how do you design systems resilient to leader election issues?**

---

**When you've thought about it, read `step-01.md`**
