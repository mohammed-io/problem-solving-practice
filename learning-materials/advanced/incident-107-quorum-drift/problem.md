---
name: incident-107-quorum-drift
description: Style quorum issues
difficulty: Advanced
category: Distributed Systems / Consistency
level: Principal Engineer
---
# Incident 107: Quorum Drift

---

## The Situation

Your distributed database uses tunable consistency:

```go
type WriteRequest struct {
    Key       string
    Value     []byte
    W         int  // Write quorum (nodes that must acknowledge)
}

type ReadRequest struct {
    Key       string
    R         int  // Read quorum (nodes to read from)
}
```

**Configuration:**
- Replication factor: 5 (data on 5 nodes)
- Default W: 3 (write to 3 nodes)
- Default R: 2 (read from 2 nodes)

---

## The Incident Report

```
Time: During node replacements

Issue: Reads returning inconsistent data (old values after writes)
Impact: Users seeing stale data, account balances wrong
Severity: P0 (data consistency issue)

Scenario:
1. Node 1 marked for replacement
2. Node 1 stops accepting writes
3. Node 6 added to cluster
4. Write with W=3 succeeds (nodes 2,3,4)
5. Read with R=2 returns old value (nodes 5,6 - neither has write!)
```

---

## What is Quorum Drift?

**Normal quorum:**
```
Replicas: [N1, N2, N3, N4, N5]
Write to W=3: N1, N2, N3
Read from R=2: N1, N2
→ At least one node (N1 or N2) has latest data
```

**Quorum drift:**
```
Replicas change: [N1, N2, N3, N4, N5] → [N2, N3, N4, N5, N6]
Write to W=3: N2, N3, N4 (write succeeds)
Read from R=2: N5, N6
→ Neither N5 nor N6 saw the write!
→ Returns stale data!
```

**The quorum calculation didn't account for replica set changing.**

---

## The Problems

### Problem 1: Replica Set Changes During Write

```
Write starts: Replicas = [1,2,3,4,5]
Select 3: [1,2,3]
Write to 1: Success
Write to 2: Success
[Topology change: Node 1 removed, Node 6 added]
Replicas now: [2,3,4,5,6]
Write to 3: Success (but 3 is still in set)
→ W=3 achieved with [1,2,3]

Read starts:
Replicas = [2,3,4,5,6]
Select 2 for read: [5,6]
→ Neither has the write!
```

### Problem 2: Read Repair Doesn't Help

```
Read repair: If R nodes disagree, use latest and update old ones
But: If none of the R nodes have the latest write, read repair can't help!
```

### Problem 3: Hinted Handoff Incomplete

```
Node 1 removed before it could sync its data to replacement Node 6
Node 6 has no data
Node 5 has no data
→ Stale read
```

---

## Jargon

| Term | Definition |
|------|------------|
| **Quorum** | Minimum nodes required for operation (R+W > RF) |
| **Quorum drift** | Replica set changes causing quorum calculations to be wrong |
| **Replication factor** | Number of nodes storing each piece of data |
| **Read repair** | Background process updating stale replicas |
| **Hinted handoff** | Temporary storage for writes meant for unavailable nodes |
| **Tunable consistency** | Adjustable R/W values per operation |
| ** sloppy quorum** | Using alternative nodes when primary replicas unavailable |

---

## Questions

1. **Why does R+W > RF guarantee consistency?** (At least one overlapping node)

2. **How does replica set change break this guarantee?**

3. **What's "sloppy quorum" and how does it relate?**

4. **How do systems like Cassandra handle this?**

5. **As a Principal Engineer, how do you prevent quorum drift?**

---

**When you've thought about it, read `step-01.md`**
