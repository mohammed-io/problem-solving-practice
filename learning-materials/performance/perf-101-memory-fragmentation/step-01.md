# Step 1: Understanding Fragmentation

---

## External vs Internal Fragmentation

**External:**
```
Free memory exists but not contiguous
Can't satisfy allocation despite having enough total free memory

Example:
Free: [10MB][20MB][15MB]  = 45MB total
Need: 30MB allocation
Result: Can't allocate! Need to grow heap
```

**Internal:**
```
Memory allocated but not used
Rounding up to size class wastes space

Example:
Request: 24 bytes
Size class: 32 bytes
Wasted: 8 bytes (internal fragmentation)
```

---

## Go's Memory Layout

```
Go m51 (=5)
|---|   <-- mcache (per thread, for small objects)
|
|---|---|---|   <-- mcentral (shared, for medium)
|
|===============|   <-- mheap (large objects, spans)

Scavenger collects from mcache
GC collects from mcentral + mheap
Fragmentation happens at span boundaries
```

---

## Common Causes

1. **Varying allocation sizes**
   ```go
   // BAD: Different sizes each time
   buf := make([]byte, rand.Intn(10000))
   ```

2. **Long-lived mixed with short-lived**
   ```go
   // Long-lived holds onto span
   longLived := make([]byte, 10<<20)
   // Short-lived keeps being allocated nearby
   for {
       temporary := make([]byte, 1<<20)
       process(temporary)
   }
   ```

3. **Keeping references to large objects**
   ```go
   var bufs [][]byte
   for i := 0; i < 1000; i++ {
       bufs = append(bufs, make([]byte, 1<<20))
   }
   // Later: bufs[500] = nil
   // But still has hole in middle!
   ```

---

## Quick Check

Before moving on, make sure you understand:

1. What's external fragmentation? (Free memory exists but not contiguous, can't allocate despite having enough total free memory)
2. What's internal fragmentation? (Memory allocated but not used, rounding up to size class wastes space)
3. What's the Go memory layout? (mcache per thread → mcentral shared → mheap for large objects)
4. What causes fragmentation? (Varying allocation sizes, mixing long/short-lived objects, keeping references to large objects)
5. Why does Go grow the heap? (When free memory exists but is too fragmented to satisfy allocation)

---

**Read `step-02.md`
