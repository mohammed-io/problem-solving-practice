# Step 2: Solutions

---

## Solution 1: Object Pools

```go
var bufferPool = sync.Pool{
    New: func() interface{} {
        return make([]byte, 1024)
    },
}

func ProcessRequest(data []byte) Response {
    buf := bufferPool.Get().([]byte)

    if len(data) > len(buf) {
        buf = make([]byte, len(data))
    }

    // Process...

    // Return to pool
    bufferPool.Put(buf)
    return Response{Data: result}
}
```

---

## Solution 2: Fixed Size Buffers

```go
// Use standard buffer sizes
const (
    KB = 1024
    MB = 1024 * KB
)

// Round up to standard size
func roundUpSize(n int) int {
    sizes := []int{1 * KB, 4 * KB, 16 * KB, 64 * KB, 256 * KB, 1 * MB, 4 * MB}
    for _, size := range sizes {
        if n <= size {
            return size
        }
    }
    return (n + MB - 1) / MB * MB  // Round to MB
}
```

---

## Solution 3: Avoid Long-Lived in Short-Lived Path

```go
// Separate hot path from cold data
type Service struct {
    // Hot: accessed frequently
    cache *Cache

    // Cold: accessed infrequently
    // Allocate separately to avoid fragmentation
    archive *Archive
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's sync.Pool? (Object pool that reuses allocations, reduces GC pressure)
2. How do you use sync.Pool? (Get() to retrieve, Put() to return, handles concurrency)
3. Why use fixed size buffers? (Reduces varying allocation sizes, decreases fragmentation)
4. Why separate hot and cold data? (Long-lived objects in hot path cause fragmentation holes)
5. What's the pattern for buffer reuse? (Get from pool, use, return to pool, handle size mismatch)

---

**Read `solution.md`
