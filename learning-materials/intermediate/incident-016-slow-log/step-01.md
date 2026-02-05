# Step 1: Analyze the Blocking Behavior

---

## The Problem

```go
// Each log line BLOCKS until written
log.Printf("BID_PROCESSING_START user_id=%d ...")  // Block: 1ms
log.Printf("BID_AMOUNT amount=%f ...")              // Block: 1ms
log.Printf("BID_CONTEXT device=%s ...")             // Block: 1ms
...
// 10 log lines × 1ms = 10ms added to latency
```

**Before:** 20ms (bid processing)
**After:** 20ms + 10ms (logging) = 30ms

But wait, the graph shows 200-500ms! **What's causing the rest?**

---

## Think About This

**What happens when disk I/O can't keep up?**

1. Application writes to stdout
2. Stdout buffer fills up
3. Application blocks waiting for buffer to flush
4. Disk is busy with other instances
5. **Wait time increases dramatically**

This is **I/O contention** - 100 instances all writing to same disk, fighting for I/O bandwidth.

---

## The Real Timeline

```
13:00-13:45: Normal operation, disk handles ~500 MB/s (100 × 5 MB/s)
14:00:      New code deployed, 100 instances start logging heavily
14:00-14:05: Disk overwhelmed, I/O queue builds up
14:05:      Latency spikes as processes wait for I/O
14:05-15:00: Death spiral - slower processing = more concurrent requests = more contention
```

---

## Questions

1. **Why does I/O contention cause exponential latency increase, not linear?**

2. **What if we log asynchronously?** (What happens on crash?)

3. **Should we just log less, or log differently?**

---

## Quick Check

Before moving on, make sure you understand:

1. What's I/O contention? (Multiple processes fighting for disk I/O bandwidth)
2. Why does latency spike non-linearly? (Queue buildup - slower processing → more concurrent → even slower)
3. What's the death spiral? (Latency ↑ → concurrent requests ↑ → memory ↑ → GC ↑ → timeout ↑)
4. What's the 10ms logging impact? (Each log line blocks 1ms, 10 lines = 10ms baseline)
5. Why is 100x worse than expected? (Disk contention causes wait, not just write time)

---

**Continue to `step-02.md`**
