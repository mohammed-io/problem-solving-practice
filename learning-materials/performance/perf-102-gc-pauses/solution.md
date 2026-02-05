# Solution: GC Pauses

---

## Root Cause

High allocation rate caused frequent GC cycles with STW pauses.

---

## Solution

**Reduce allocations + tune GOGC:**

```go
// 1. Enable detailed GC stats
import _ "net/http/pprof"

// 2. Use object pools for hot paths
// 3. Escape analysis: keep variables on stack
func Process() (Result, error) {
    // Allocate on stack if possible
    var buf [1024]byte
    // ...
    return Result{}, nil
}

// 4. Tune for latency vs throughput
// GOGC=200 for fewer GCs (better latency, more memory)
// GOGC=50 for more GCs (lower memory, more CPU)
```

---

**Monitoring:**
```bash
# GC stats
curl localhost:6060/debug/pprof/heap
go tool pprof -http=:8080 heap
```

---

**Next Problem:** `performance/perf-103-cpu-throttling/`
