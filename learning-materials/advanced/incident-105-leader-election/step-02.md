# Step 2: Raft and Fencing

---

## Raft's Solution: Terms + Quorum

```
Election with term numbers:

Term 1:
  All nodes start at term 1
  Node 5 starts election, gets 3 votes (quorum)
  Node 5 becomes leader for term 1

Term 2 (if leader crashes):
  Node 3 starts election with term 2
  Gets 3 votes, becomes leader
```

**Properties:**
1. Term numbers always increase
2. Higher term wins
3. Quorum prevents split brain

---

## Fencing Tokens

**Problem:** Old leader doesn't know it's been deposed

```
Leader in partition {1,2} (term 1)
  → Writes to database with fencing token=1

Partition heals
  → New leader elected (term 2)

Old leader returns
  → Tries to write with token=1
  → Database rejects: "token 1 < current token 2"
```

**Implementation:**
```go
// Each write includes term/epoch token
type WriteRequest struct {
    Key   string
    Value string
    Term  int64  // Fencing token
}

func (s *Server) HandleWrite(req WriteRequest) error {
    if req.Term < s.currentTerm {
        return ErrStaleLeader
    }
    s.storage.Set(req.Key, req.Value)
    return nil
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What is Raft's term number? (Monotonically increasing election epoch)
2. How do terms prevent split brain? (Higher term always wins)
3. What is a fencing token? (Monotonic value that invalidates old leaders)
4. How do fencing tokens work? (Include with writes, reject stale tokens)
5. Why are fencing tokens needed? (Old leader may not know it was deposed)

---

**Continue to `solution.md`**
