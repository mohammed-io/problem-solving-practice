# Solution: Leader Election Gone Wrong

---

## Root Cause

**Three failures:**
1. No quorum requirement (minority partition elected leader)
2. No term numbers (can't detect stale leader)
3. No fencing (old leader can still make changes)

---

## Complete Solution: Use Raft

### Raft Leader Election

```go
type RaftNode struct {
    id        int
    peers     []int
    state     string  // "follower", "candidate", "leader"
    currentTerm int64
    votedFor  int
    votes     map[int]bool
    heartbeat time.Duration
    electionTimeout time.Duration
}

func (n *RaftNode) StartElection() {
    n.state = "candidate"
    n.currentTerm++
    n.votedFor = n.id

    // Request votes from all peers
    votes := 1  // Vote for self
    for _, peer := range n.peers {
        if n.requestVote(peer) {
            votes++
        }
    }

    // Need quorum: majority of nodes
    quorum := len(n.peers)/2 + 1
    if votes >= quorum {
        n.state = "leader"
        n.sendHeartbeats()
    } else {
        n.state = "follower"
    }
}

func (n *RaftNode) requestVote(peer int) bool {
    req := VoteRequest{
        term:        n.currentTerm,
        candidateID: n.id,
    }

    resp := sendRPC(peer, "RequestVote", req)

    // If peer's term is higher, we lose election
    if resp.term > n.currentTerm {
        n.currentTerm = resp.term
        n.state = "follower"
        return false
    }

    return resp.voteGranted
}
```

### Fencing Implementation

```go
// Distributed lock with fencing
func AcquireLockWithFencing(resource string) (int64, error) {
    // Get current epoch (term)
    epoch := getCurrentEpoch()

    // Try to acquire lock
    script := `
        local key = KEYS[1]
        local epoch = ARGV[1]
        local owner = redis.call("HGET", key, "owner")

        if owner == false or redis.call("HGET", key, "epoch") < epoch then
            redis.call("HMSET", key, "owner", ARGV[2], "epoch", epoch)
            redis.call("EXPIRE", key, 10)
            return epoch
        else
            return nil
        end
    `

    result, err := redis.Eval(script, []string{"lock:" + resource},
        epoch, myNodeID).Result()

    if err != nil || result == nil {
        return 0, errors.New("lock not acquired")
    }

    return result.(int64), nil
}

// Every write includes fencing token
func WriteWithFencing(key, value string, token int64) error {
    currentToken := getCurrentToken(key)
    if token < currentToken {
        return ErrStaleWrite
    }
    // Perform write
    return storage.Set(key, value)
}
```

---

## Systemic Prevention

### 1. Use Established Consensus Libraries

**Don't implement leader election yourself!**

| Language | Library |
|----------|---------|
| Go | hashicorp/raft |
| Java | atomix/raft |
| Python | pysyncobj |
| C++ | asyncchop/raft |

### 2. Lease-Based Leadership

```go
// Leadership is time-bounded
func (n *RaftNode) MaintainLeadership() {
    ticker := time.NewTicker(n.heartbeat / 2)
    for {
        select {
        case <-ticker.C:
            if n.state == "leader" {
                // Renew lease
                if !n.renewLease() {
                    // Lost leadership
                    return
                }
            }
        }
    }
}

// Check if still leader before each operation
func (n *RaftNode) IsLeader() bool {
    if n.state != "leader" {
        return false
    }
    if time.Since(n.leaseRenewed) > n.leaseTimeout {
        n.state = "follower"
        return false
    }
    return true
}
```

### 3. Monitoring

```promql
# Multiple leaders detected (alert immediately!)
- alert: MultipleLeaders
  expr: |
    count(raft_leader==1) > 1
  labels:
    severity: critical

# Term changes frequently (unstable)
- alert: HighTermChanges
  expr: |
    rate(raft_term_changes[5m]) > 0.1
  labels:
    severity: warning

# Node thinks it's leader but no quorum
- alert: LeaderWithoutQuorum
  expr: |
    raft_leader == 1 and raft_peers_connected < (raft_peers_total / 2 + 1)
  labels:
    severity: critical
```

---

## Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| **Raft** | Proven, split-brain proof | Complexity, latency for coordination |
| **Bully algorithm** | Simple | Split brain possible |
| **Lease-based** | Auto-recovery on timeout | Lease expiry vs clock skew issues |
| **Fencing tokens** | Prevents old leaders | Requires storage/infrastructure support |

**Recommendation:** Use Raft or an established library. Add fencing tokens for write-sensitive systems.

---

**Next Problem:** `advanced/incident-106-backpressure/`
