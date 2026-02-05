# Step 01

---

## Understanding Raft Elections

In Raft, a node becomes leader when:
1. It discovers no current leader (missed heartbeats)
2. It increments its term
3. It requests votes from peers
4. It receives votes from **majority** of nodes

**Key insight:** Raft elections require **communication** between nodes.

---

## What Happened During the Partition

```
Before partition (2:14:55):
┌─────┐ ┌─────┐ ┌─────┐
│ 1a  │→│ 1b  │→│ 1c  │   All see each other, 1a is leader
└─────┘ └─────┘ └─────┘
  term=5

During partition (2:15:01):
┌─────┐   X   X   X     1a can't see 1b, 1c
│ 1a  │
└─────┘
  X   X   X     No communication!

  X   X   X

After (2:15:03):
┌─────┐   X   X   X     1a thinks it's alone
│ 1a  │             → Starts election
└─────┘
  ↑   ↑   ↑
  1b 1c (also can't see each other or 1a)

Each zone says: "I can't see the leader, I must be leader!"
```

---

## The Bug

Look at the election code again:

```go
func (n *Node) startElection() {
  n.votesNeeded = len(n.peers) / 2 + 1  // Calculate quorum

  for _, peer := range n.peers {
    go n.requestVote(peer)  // Async requestVote to peers
  }

  // No waiting for responses!
  n.becomeLeader()  // BUG: Becomes leader immediately
}
```

**The bug:** The code doesn't wait for vote responses!

It calculates `votesNeeded = 2` but immediately becomes leader without actually getting the votes.

---

## What Should Happen

Correct Raft election flow:

1. Start election (become candidate)
2. **Request votes from peers**
3. **Wait for responses**
4. **Count votes received**
5. **Only become leader if votes >= quorum**

In a 3-node cluster:
- Quorum = 2 (majority)
- Need 2 votes (including self)
- Only ONE zone can get 2 votes

---

## Why 1b Also Became Leader

Zone 1b saw the same network blurb:
- Couldn't see 1a or 1c
- Started its own election
- **Same bug**: became leader without waiting for votes

Result: **Two leaders** because both nodes had the same bug.

---

## Quick Check

Before moving on, make sure you understand:

1. What is quorum in a 3-node Raft cluster? (2 nodes - majority of 3)
2. What was the bug in the election code? (Became leader without waiting for votes)
3. Why did both 1a and 1b become leader? (Same bug - both became leader without quorum)
4. What's the purpose of the term number in Raft? (Logical clock that increments, higher term wins)
5. Why does Raft require communication between nodes? (To count votes and ensure only one leader)

---

**Want to see the recovery? Read `step-02.md`**
