# Step 1: GC in Go

---

## How Go GC Works

```
1. Mark phase (concurrent):
   - Finds reachable objects
   - Runs mostly concurrently with app

2. Sweep phase (concurrent):
   - Reclaims unused memory
   - Runs in background

3. BUT: Some STW pauses remain
   - Mark start: short STW to prepare
   - Mark termination: STW to finish
   - Some stack scanning: STW
```

---

## GOGC Setting

```
GOGC=100 (default)
  Trigger GC when heap grows 100% since last GC

GOGC=200
  Trigger GC when heap grows 200%
  Fewer GCs, but each GC takes longer

GOGC=off
  Disable GC (dangerous!)
```

---

## Quick Check

Before moving on, make sure you understand:

1. What are the GC phases? (Mark: find reachable objects, Sweep: reclaim memory)
2. What's STW? (Stop-the-world pause where application halts during GC)
3. What's GOGC? (Percentage of heap growth that triggers GC, default 100)
4. What's concurrent GC? (GC runs mostly while app continues, but some STW pauses remain)
5. What happens with GOGC=off? (GC disabled, memory never reclaimed, dangerous)

---

## Read `step-02.md`
