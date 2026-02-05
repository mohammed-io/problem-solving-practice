# Step 1: The Quorum Problem

---

## Why Quorum Matters

**Without quorum:**
```
5 nodes: [1, 2, 3, 4, 5]
Partition: {1, 2} | {3, 4, 5}

Node 2: "I see 2 nodes, I'm leader!"
Node 5: "I see 3 nodes, I'm leader!"
→ Both claim leadership → Split brain!
```

**With quorum:**
```
Quorum = 3 (majority of 5)

Node 2: "I see 2 nodes, not enough for quorum, wait"
Node 5: "I see 3 nodes, quorum achieved, I'm leader!"
→ Only one leader!
```

---

## The Math

For N nodes, quorum = ⌊N/2⌋ + 1

```
N=3:  quorum=2  (need 2 of 3)
N=5:  quorum=3  (need 3 of 5)
N=7:  quorum=4  (need 4 of 7)
```

**Key insight:** Two partitions can BOTH achieve quorum? NO!

```
Split {1,2} and {3,4,5}:
- {1,2}: 2 < 3 (no quorum)
- {3,4,5}: 3 >= 3 (quorum!)
```

Only one partition can have quorum. Only one leader elected.

---

## Quick Check

Before moving on, make sure you understand:

1. What is quorum? (Majority of nodes: ⌊N/2⌋ + 1)
2. Why does quorum prevent split brain? (Only one partition can have majority)
3. Can two partitions both achieve quorum? (No, by definition majority)
4. What happens without quorum? (Multiple leaders elected, split brain)
5. What's the quorum for 7 nodes? (4 = ⌊7/2⌋ + 1)

---

**Continue to `step-02.md`**
