# Solution: Split Brain - Raft Implementation Bug

---

## Root Cause

**Improper Raft election implementation** - nodes became leader without achieving quorum.

### The Bug

```go
func (n *Node) startElection() {
  n.votesNeeded = len(n.peers) / 2 + 1

  // Async requestVote - doesn't wait!
  for _, peer := range n.peers {
    go n.requestVote(peer)
  }

  // BUG: Immediately becomes leader
  // Should wait for votes to be collected!
  n.becomeLeader()
}
```

The code:
1. Calculates quorum correctly (2 votes needed)
2. **Never waits** for responses
3. **Immediately becomes leader**

Result: Any node that thinks it's alone becomes "leader" immediately.

---

## The Fix

### Immediate: Manual Intervention

```bash
# SSH into each node and stop the process
# 1. Determine the REAL leader (lowest term number, or connected to DB)
# 2. Stop the wrong leaders

kubectl exec -it pod/payment-1c-1a -- kill -SIGTERM 1

# Or use Raft CLI if available
raft-cli remove-peer node-1b
raft-cli remove-peer node-1c
```

### Code Fix: Proper Vote Counting

```go
func (n *Node) startElection() {
  n.state = "candidate"
  n.currentTerm++

  // Vote for self
  n.votes[n.id] = true
  n.votesNeeded = len(n.peers)/2 + 1

  // Request votes synchronously with timeout
  for _, peer := range n.peers {
    if n.requestVoteSync(peer, time.Second) {
      n.votes[peer] = true
    }
  }

  // Only become leader if we have quorum
  if len(n.votes) >= n.votesNeeded {
    n.becomeLeader()
  } else {
    n.state = "follower"
  }
}
```

---

## Systemic Prevention (Staff Level)

### 1. Use Established Libraries

**Don't implement Raft yourself!**

| Language | Raft Library |
|----------|--------------|
| Go | `hashicorp/raft` |
| Java | `atomix/raft` |
| Python | `rapyuta` |
| C++ | `asyncchop/raft` |

These libraries have been tested in production for years.

### 2. Add Leader Lease

Even after winning election, wait for a "leader lease":

```go
func (n *Node) becomeLeader() {
  // Wait for distributed lock
  lease, err := n.acquireLeaderLease(10 * time.Second)
  if err != nil {
    return // Someone else is leader
  }

  n.state = "leader"
  n.leaderLease = lease

  // Renew lease periodically
  go n.renewLease()

  // Now accept writes
  n.allowWrites = true
}
```

If network partitions and node can't renew lease, it stops being leader.

### 3. Add Fencing Tokens

When a node thinks it's leader, it must verify with database:

```go
func (n *Node) becomeLeader() {
  // Write fencing token to database
  fenceToken := uuid.New().String()
  db.Exec("INSERT INTO fencing_tokens (node_id, token, expires_at) VALUES ($1, $2, NOW() + 30)", n.id, fenceToken)

  // Every write includes this token
  // Database rejects writes from nodes with expired tokens
}
```

### 4. Monitoring

Alert on:
- Multiple nodes claiming to be leader
- Nodes with term number > current term + 1
- Leader election frequency (should be rare)

---

## Real Incident

**AWS (2011)**: Network partition in US-EAST-1 caused EBS volumes in one AZ to become unavailable. Applications using "auto-leader" pattern created split brain where multiple nodes thought they were leader, causing data divergence.

---

## Jargon

| Term | Definition |
|------|------------|
| **Split brain** | Multiple nodes think they're the leader simultaneously; causes data inconsistency |
| **Network partition** | Network failure preventing communication between nodes in distributed system |
| **Leader election** | Process of selecting single coordinator; requires quorum to prevent split brain |
| **Quorum** | Majority of nodes (N/2 + 1); required for decisions in Raft |
| **Term** | Logical clock in Raft; increments on each election; higher term wins |
| **Heartbeat** | Periodic "I'm alive" message; missed heartbeats trigger election |
| **Leader lease** | Time-bounded leadership; must be renewed or leadership is lost |
| **Fencing token** | Value stored in shared storage (DB) that only leader can update; prevents old leaders from making changes |
| **Raft** | Consensus algorithm for distributed systems; ensures strong consistency |
| **Data divergence** | When different nodes have different data for same entity (bad!) |

---

**Next Problem:** `intermediate/incident-011-replica-lag/`
