# Step 2: Replication and Consistency

---

## Replication Factor

How many copies of each piece of data?

**Replication factor = 3** (common choice):
- Each key stored on 3 different nodes
- Can tolerate 2 node failures
- More replicas = more cost, more consistency challenges

## Write Strategies

### Write Quorum (W)

How many nodes must acknowledge write?

```
W=1: Write to 1 node, acknowledge immediately (fast, risky)
W=2: Write to 2 nodes, acknowledge (safer)
W=3: Write to all 3 nodes (slowest, safest)
```

### Read Quorum (R)

How many nodes to read from?

```
R=1: Read from 1 node (fast, might be stale)
R=2: Read from 2 nodes, compare (slower, more consistent)
R=3: Read from all 3 nodes (slowest, most consistent)
```

## Consistency Level

If R + W > Replication Factor, you get **strong consistency**:
```
RF=3, R=2, W=2 → 2+2=4 > 3 = Strong consistency
(at least one node overlaps)
```

If R + W ≤ Replication Factor, you get **eventual consistency**:
```
RF=3, R=1, W=1 → 1+1=2 < 3 = Eventual consistency
(might read from node that hasn't received write yet)
```

---

## Hinted Handoff

What if a node is down during write?

```
Writing to nodes [A, B, C] but B is down:
1. Write to A and C
2. Store write for B in hint on A
3. When B recovers, A pushes hint to B
```

This ensures writes aren't lost even during node failures.

---

## Quick Check

Before moving on, make sure you understand:

1. What's replication factor? (Number of copies of each piece of data)
2. What's write quorum (W)? (How many nodes must acknowledge a write)
3. What's read quorum (R)? (How many nodes to read from)
4. When do you get strong consistency? (When R + W > replication factor)
5. What's hinted handoff? (Storing write hints for unavailable nodes to deliver later)

---

**Continue to `solution.md`**
