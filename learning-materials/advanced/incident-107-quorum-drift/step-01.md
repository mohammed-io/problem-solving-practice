# Step 1: Understanding R+W > RF

---

## The Consistency Condition

For strong consistency: **R + W > Replication Factor**

```
RF = 5 (replicas)
W = 3 (write quorum)
R = 2 (read quorum)

2 + 3 = 5 > 5 ✓
```

**Why this works:**
- Write goes to 3 nodes: [1,2,3]
- Read from 2 nodes
- Worst case: Read from [4,5] (neither has write)
- But R=2, we read 2 nodes
- Probability of both being [4,5]: Only if we deliberately avoid [1,2,3]!
- With random selection, we'll likely hit at least one of [1,2,3]

**Actually:** The guarantee is: **At least one node in read set is in write set**

---

## Where It Breaks

```
Write at time T1 to replicas [1,2,3]
Replica set changes at T2: [1,2,3,4,5] → [2,3,4,5,6]
Read at time T3 from replicas [5,6]

At T3: We read from [5,6]
At T3: Neither [5] nor [6] was in write set [1,2,3] at T1!
BUT: The formula R+W > RF was calculated assuming same replica set!
```

**The quorum condition only holds if replica set is stable!**

---

## Quick Check

Before moving on, make sure you understand:

1. What is the R+W > RF condition? (Read + Write quorum > replication factor)
2. Why does this guarantee consistency? (At least one read node was written to)
3. When does this break? (Replica set changes between write and read)
4. What is "quorum drift"? (Topology changes invalidate quorum assumptions)
5. Why is the formula insufficient? (Assumes stable replica set)

---

**Continue to `step-02.md`**
