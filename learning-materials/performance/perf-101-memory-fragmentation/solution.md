# Solution: Memory Fragmentation

---

## Root Cause

Varying allocation sizes and mixed object lifetimes caused heap fragmentation.

---

## Solution

**Use object pools + fixed sizes:**

```go
// Pool for buffers
var bufPool = sync.Pool{
    New: func() interface{} {
        b := make([]byte, 0, 64*1024)  // 64KB capacity
        return &b
    },
}

func GetBuffer() *[]byte {
    return bufPool.Get().(*[]byte)
}

func PutBuffer(b *[]byte) {
    // Reset but keep capacity
    *b = (*b)[:0]
    bufPool.Put(b)
}

// For large allocations, consider off-heap
// - Use mmap for very large buffers
// - Keep separate from GC heap
```

**Monitoring:**

```bash
# Check fragmentation
GODEBUG=gctrace=1 ./app

# Look for:
# - "forced" GC = memory pressure
# - Large RSS vs heap = fragmentation
# - Growing heap frequently
```

---

**Next Problem:** `performance/perf-102-gc-pauses/`
