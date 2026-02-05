# Step 02: Recovery and Prevention

---

## Recovery From Split Brain

### Immediate: Identify True Leader

**1. Check database connections:**
```bash
# Which nodes are actually writing to the database?
grep "INSERT INTO payment_events" /var/log/payment-service/*.log | tail -20

# Or check database directly
SELECT node_id, COUNT(*), MAX(timestamp)
FROM payment_events
GROUP BY node_id
ORDER BY MAX(timestamp) DESC;
```

**2. Stop the wrong leaders:**
```bash
# Zone 1c is not writing to DB (or writing with old fence token)
kubectl delete pod payment-1c-1a -n payment
```

**3. Verify single leader:**
```bash
# Check Raft state
curl http://payment-1b:8080/v1/state
# Should return: {"state": "leader", "term": 6}

curl http://payment-1a:8080/v1/state
# Should return: {"state": "follower", "term": 6}
```

---

## Long-term Fixes

### 1. Fix the Raft Implementation

```go
func (n *Node) startElection() {
  n.state = "candidate"
  n.currentTerm++

  // Vote for self
  n.votes[n.id] = true
  n.votesNeeded = len(n.peers)/2 + 1

  // Request votes SYNCHRONOUSLY
  votesReceived := 1  // Our vote

  for _, peer := range n.peers {
    if n.requestVoteSync(peer, 2*time.Second) {
      votesReceived++
    }
  }

  // Only become leader if quorum achieved
  if votesReceived >= n.votesNeeded {
    n.becomeLeader()
  } else {
    n.state = "follower"
  }
}
```

### 2. Use Established Raft Library

**Don't implement Raft yourself!**

```go
// Use hashicorp/raft
import "github.com/hashicorp/raft"

// Configure Raft
config := raft.DefaultConfig()
config.LocalID = "node-1"

// Create transport
transport, _ := raft.NewTCPTransport("127.0.0.1:8080", nil, 3, 10*time.Second, os.Stderr)

// Create Raft instance
raftNode, _ := raft.NewRaft(
  config,
  &fsm{},  // Finite state machine
  transport,
  store,
  store,
  snapshotStore,
  peerStore,
)

// Apply changes (Raft handles consensus)
raftNode.Apply([]byte("data"), 5*time.Second)
```

### 3. Add Leader Lease

```go
func (n *Node) becomeLeader() {
  // Wait for leader lease before accepting writes
  lease, err := n.acquireLeaderLease(10 * time.Second)
  if err != nil {
    log.Printf("Failed to acquire lease: %v", err)
    n.state = "follower"
    return
  }

  n.state = "leader"
  n.leaderLease = lease

  // Renew lease periodically
  go n.renewLease()

  // Only now accept writes
  n.allowWrites = true
}
```

### 4. Add Fencing Tokens

```go
func (n *Node) processWrite(data WriteData) error {
  // Verify we still hold leadership
  if !n.verifyLeadership() {
    return ErrNotLeader
  }

  // Include fencing token in write
  data.FencingToken = n.fencingToken

  // Database verifies token
  err := n.db.Write(data)
  if err == ErrInvalidFencingToken {
    // Someone else is leader!
    n.state = "follower"
    return ErrNotLeader
  }

  return nil
}
```

---

## Monitoring to Catch Split Brain Early

```yaml
# Prometheus alerts
groups:
  - name: raft
    rules:
      - alert: MultipleLeaders
        expr: count(raft_state{state="leader"}) > 1
        for: 10s
        annotations:
          summary: "Split brain detected - multiple leaders!"

      - alert: HighElectionRate
        expr: rate(raft_election_count[5m]) > 0.1
        for: 5m
        annotations:
          summary: "Frequent elections may indicate network issues"

      - alert: LeaderFencingFailed
        expr: rate(fencing_token_failures[1m]) > 0
        for: 1m
        annotations:
          summary: "Leadership fencing failures - possible split brain"
```

---

## Summary

| Fix Type | Solution | When to Use |
|----------|----------|-------------|
| **Immediate** | Identify true leader, stop others | During incident |
| **Code fix** | Wait for quorum before becoming leader | If implementing Raft |
| **Best practice** | Use established Raft library | Always |
| **Safety** | Add leader lease + fencing tokens | Production |
| **Monitoring** | Alert on multiple leaders | Always |

---

## Quick Check

Before moving on, make sure you understand:

1. What's the immediate fix for split brain? (Identify true leader, stop wrong leaders)
2. What's the code fix for Raft election? (Wait for votes, only become leader if quorum achieved)
3. Why use established Raft libraries? (They're tested in production, handle edge cases)
4. What's a leader lease? (Time-bounded leadership that must be renewed)
5. What's a fencing token? (Value in shared storage that only leader can update, prevents old leaders)

---

**Now read `solution.md` for complete reference.**
