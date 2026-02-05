# Step 1: Analyze the Retry Pattern

---

## The Problem

Transaction abc123 always acquires locks in this order:
```
Lock(user-123) → Lock(user-456)
```

Transaction def456 always acquires locks in this order:
```
Lock(user-456) → Lock(user-789)
```

When both run simultaneously:
```
abc123: Lock(user-123) → waits for user-456
def456: Lock(user-456) → waits for user-789
```

Wait, there's no deadlock here yet. Let's look at the full cycle:

```
ghi789: Lock(user-789) → Lock(user-123)
```

Now we have:
```
abc123 → user-456 (held by def456)
def456 → user-789 (held by ghi789)
ghi789 → user-123 (held by abc123)
↺ CYCLE! ↺
```

Killing abc123 doesn't help because:
1. abc123 retries as abc124
2. abc124 locks user-123 again
3. Same cycle forms

---

## The Insight

**The deadlock is in the lock acquisition order**, not just bad luck.

If all transactions lock in the **same order**, no deadlock is possible.

But in this system, different transactions have different lock orders based on business logic.

---

## Quick Check

Before moving on, make sure you understand:

1. What is "phoenix deadlock"? (Deadlock recurs after retry because lock order is broken)
2. Why does killing a transaction not help? (Retry locks same resources in same order)
3. What's the root cause? (Different transactions have different lock acquisition orders)
4. Can consistent lock ordering help here? (Yes, if ALL transactions use same order)
5. What if business logic requires different orders? (Need wait-die or wound-wait schemes)

---

**Continue to `step-02.md`**
