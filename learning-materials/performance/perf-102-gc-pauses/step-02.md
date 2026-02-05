# Step 2: Reducing GC Pressure

---

## Strategy 1: Allocate Less

```go
// BAD: Allocates per request
func Process(data []byte) Result {
    tmp := make([]byte, len(data))
    // ...
}

// GOOD: Reuse buffers
var bufPool = sync.Pool{
    New: func() interface{} {
        return make([]byte, 0, 4096)
    },
}

func Process(data []byte) Result {
    buf := bufPool.Get().([]byte)
    defer bufPool.Put(buf)
    // ...
}
```

---

## Strategy 2: Avoid Pointer-Heavy Structs

```go
// BAD: Many pointers
type Data struct {
    A *int
    B *int
    C *int
    // 100 pointers = 100 words to scan
}

// GOOD: Use values
type Data struct {
    A int
    B int
    C int
    // 100 values = 100 words but better cache behavior
}
```

---

## Strategy 3: Use Off-Heap

```go
// For very large data, use syscall mmap
// or consider C malloc via cgo
// Data allocated outside GC heap
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's the best way to reduce GC pressure? (Allocate less - reuse buffers with sync.Pool)
2. Why avoid pointer-heavy structs? (More pointers = more scanning time during GC mark phase)
3. What's off-heap memory? (Memory allocated outside GC heap, not scanned by GC)
4. How does sync.Pool help? (Reuses allocations, reduces GC workload by reusing objects)
5. What's the tradeoff with value types vs pointers? (Values use less GC but may cause copying)

---

**Read `solution.md`
