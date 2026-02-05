---
name: perf-102-gc-pauses
description: GC Pauses
difficulty: Advanced
category: Performance / GC / Latency
level: Senior Engineer
---
# Performance 102: GC Pauses

---

## Tools & Prerequisites

To debug GC-related latency issues:

### GC Profiling Tools

| Tool | Purpose | Quick Usage |
|------|---------|-------------|
| **GODEBUG=gctrace=1** | Go GC tracing | `GODEBUG=gctrace=1 ./app` |
| **go tool pprof** | CPU/Memory profiling | `go tool pprof http://localhost:6060/debug/pprof/heap` |
| **go tool trace** | Execution tracing | `go test -trace=trace.out` |
| **runtime.ReadMemStats()** | In-code memory stats | Log every N seconds |
| **GC stats viewer** | Visualize GC logs | `gcviewer` for JVM |
| **JVisualVM / JConsole** | JVM monitoring | Connect to running JVM |
| **async-profiler** | Java/C++ profiling | `profiler.sh -d 30 -f cpu.flamegraph pid` |

### Key Commands

```bash
# Go GC tracing
GODEBUG=gctrace=1 ./app
# Output: gc 1 @0.001s 2%: 0.016+0.46+0.054 ms clock, 0.13+3.6+0.43 ms cpu

# Go memory profiling
curl http://localhost:6060/debug/pprof/heap > heap.prof
go tool pprof heap.prof

# Go execution tracing
go test -trace=trace.out
go tool trace trace.out

# JVM GC monitoring
jstat -gcutil <pid> 1000 10
# Output: S0C S1C S0U S1U EC EU OC OU MC MU CCSC CCSU YGC YGCT FGC FGCT GCT

# JVM GC logging
java -Xlog:gc*:file=gc.log -jar app.jar

# View JVM GC details
jmap -heap <pid>
```

### Key Concepts

**Stop-The-World (STW)**: GC pauses all application threads while performing collection.

**Mark Phase**: GC finds all reachable (live) objects from root references.

**Sweep Phase**: GC reclaims memory from unreachable (dead) objects.

**Concurrent GC**: GC runs concurrently with application execution, reducing STW time.

**Parallel GC**: Multiple GC threads work in parallel during STW phase.

**GOGC**: Go's GC trigger; runs when heap grows by GOGC% since last GC (default 100).

**Generational GC**: Divides heap into young/old generations; collects young more frequently.

**Object Pooling**: Reuse objects instead of allocating new ones; reduces GC pressure.

**Escape Analysis**: Compiler determines if object can be stack-allocated (no GC overhead).

**Card Table**: Data structure tracking generational references (old gen → young gen).

---

## Visual: GC Pauses

### Stop-The-World GC Impact

```mermaid
sequenceDiagram
    autonumber
    participant App as Application
    participant GC as Garbage Collector

    Note over App,GC: Normal execution
    App->>App: Processing requests...

    Note over App,GC: Heap reaches threshold!
    App->>GC: Trigger GC
    GC->>App: ⏸️ STOP THE WORLD
    App->>App: (paused)

    GC->>GC: Mark phase (find live objects)
    GC->>GC: Sweep phase (reclaim memory)

    GC->>App: ▶️ RESUME
    App->>App: Processing requests...

    Note over App: Latency spike during pause!
```

### Generational GC

```mermaid
flowchart TB
    subgraph Heap ["Heap Layout"]
        Young["Young Generation<br/>(Eden + Survivor Spaces)"]
        Old["Old/Tenured Generation<br/>(Long-lived objects)"]

        Eden["Eden Space<br/>(New allocations)"]
        S0["Survivor S0"]
        S1["Survivor S1"]

        Young --> Eden
        Young --> S0
        Young --> S1
    end

    subgraph Flow ["Object Lifecycle"]
        Alloc["New object in Eden"]
        MinorGC["Minor GC (Young gen only)"]
        Promote["Promote to Old gen"]
        MajorGC["Major GC (Full GC)"]

        Alloc -->|"Survive N GCs"| Promote
        Alloc --> MinorGC
        MinorGC -->|"Die"| Reclaim["Reclaimed"]
        Promote --> MajorGC
    end

    style Young fill:#c8e6c9
    style Old fill:#fff3e0
    style Reclaim fill:#ffcdd2
```

### GC Pause Over Time

**GC Pause Duration vs Heap Size**

| Heap Size | Pause Time (ms) |
|-----------|-----------------|
| 10MB | 1 |
| 100MB | 5 |
| 500MB | 25 |
| 1GB | 50 |
| 2GB | 100 |
| 4GB | 180 |

### Concurrent vs Parallel GC

```mermaid
flowchart TB
    subgraph SerialGC ["Serial GC (Single Thread)"]
        SG1["Mark: Single thread"]
        SG2["Sweep: Single thread"]
        SG3["Long pause, low CPU"]

        SG1 --> SG2 --> SG3
    end

    subgraph ParallelGC ["Parallel GC (Multi-threaded STW)"]
        PG1["Mark: Multiple threads"]
        PG2["Sweep: Multiple threads"]
        PG3["Shorter pause, high CPU"]

        PG1 --> PG2 --> PG3
    end

    subgraph ConcurrentGC ["Concurrent GC (Mostly Concurrent)"]
        CG1["Mark: Concurrent with app"]
        CG2["Short STW for roots"]
        CG3["Sweep: Concurrent"]
        CG4["Minimal pause, consistent CPU"]

        CG1 --> CG2 --> CG3 --> CG4
    end

    style SerialGC fill:#ffcdd2
    style ParallelGC fill:#fff3e0
    style ConcurrentGC fill:#c8e6c9
```

### Object Pooling Impact

**GC Frequency: With vs Without Object Pooling**

| Time (seconds) | Without Pooling (MB) | With Pooling (MB) |
|----------------|---------------------|-------------------|
| 0 | 100 | 50 |
| 1 | 200 | 80 |
| 2 | 300 | 100 |
| 3 | 400 | 120 |
| 4 | 500 | 140 |
| 5 | 100 | 50 |
| 6 | 200 | 80 |
| 7 | 300 | 100 |

Without pooling: Heap grows to 500MB before GC. With pooling: Max 140MB.

### Escape Analysis Example

```mermaid
flowchart TB
    subgraph NoEscape ["No Escape (Stack Allocated)"]
        NE1["func foo() int {<br/>  x := 100<br/>  return x<br/>}"]
        NE2["✅ Stack allocated"]
        NE3["✅ No GC overhead"]
        NE4["✅ Auto cleanup on return"]

        NE1 --> NE2 --> NE3 --> NE4
    end

    subgraph Escapes ["Escapes to Heap"]
        E1["func foo() *int {<br/>  x := 100<br/>  return &x<br/>}"]
        E2["❌ Heap allocated"]
        E3["❌ GC must track"]
        E4["❌ Cleanup via GC"]

        E1 --> E2 --> E3 --> E4
    end

    style NoEscape fill:#c8e6c9
    style Escapes fill:#ffcdd2
```

### GOGC Tuning

```mermaid
flowchart LR
    subgraph LowGOGC ["GOGC=50 (Conservative)"]
        L1["Trigger at 50% growth"]
        L2["Frequent GC"]
        L3["Small pauses"]
        L4["Higher CPU overhead"]

        L1 --> L2 --> L3 --> L4
    end

    subgraph DefaultGOGC ["GOGC=100 (Default)"]
        D1["Trigger at 100% growth"]
        D2["Balanced"]
        D3["Moderate pauses"]

        D1 --> D2 --> D3
    end

    subgraph HighGOGC ["GOGC=200 (Aggressive)"]
        H1["Trigger at 200% growth"]
        H2["Infrequent GC"]
        H3["Large pauses"]
        H4["Lower CPU overhead"]

        H1 --> H2 --> H3 --> H4
    end

    style LowGOGC fill:#e8f5e9
    style DefaultGOGC fill:#fff3e0
    style HighGOGC fill:#ffcdd2
```

### GC Optimization Strategies

```mermaid
graph TB
    subgraph Strategies ["GC Optimization Strategies"]
        S1["🎯 Object Pooling<br/>Reuse buffers/objects"]
        S2["📊 Pre-allocate capacity<br/>make([]T, 0, size)"]
        S3["🔍 Escape Analysis<br/>Avoid pointers in hot paths"]
        S4["📦 Value types over references<br/>struct vs pointer"]
        S5["⏱️ Tune GOGC<br/>(or disable for short bursts)"]
        S6["🧵 Use workers<br/>(sync.Pool)"]
    end

    style Strategies fill:#e8f5e9
```

### Sync.Pool Usage Pattern

```mermaid
sequenceDiagram
    autonumber
    participant App as Application
    participant Pool as sync.Pool

    Note over App,Pool: Without Pool (allocates every time)
    App->>App: New buffer
    App->>App: Use buffer
    App->>App: Buffer discarded → GC work

    Note over App,Pool: With Pool (reuses buffers)
    App->>Pool: Get() from pool
    Pool-->>App: Reused buffer
    App->>App: Use buffer
    App->>Pool: Put(buffer) back
    Note over Pool: Buffer reused, no allocation!
```

---

## The Incident

Your low-latency trading system has P99 latency of 10ms... except for occasional 100ms spikes.

```
Latency profile:
P50: 1ms
P90: 3ms
P95: 5ms
P99: 8ms
P99.9: 150ms  ← SPIKES!

Analysis: Spikes correlate with GC "stop the world" pauses
```

---

## The Jargon

| Term | Definition |
|------|------------|
| **STW** | Stop-the-world - all goroutines paused during GC |
| **Mark** | Finding reachable objects |
| **Sweep** | Reclaiming unused memory |
| **Concurrent GC** | GC runs alongside application |
| **GOGC** | Percentage of heap growth before GC triggers |
| **Generational** | Heap divided into young/old generations |
| **Object Pool** | Reuse objects to reduce allocations |
| **Escape Analysis** | Compiler optimization for stack allocation |

---

## Questions

1. **What causes GC pauses?** (Mark/sweep phases, heap size)

2. **How does GOGC affect pause frequency?** (Higher = less frequent but larger pauses)

3. **What's the difference between concurrent and parallel GC?** (Concurrent runs with app, parallel uses threads)

4. **How do you reduce GC pressure?** (Object pooling, escape analysis, value types)

5. **As a Senior Engineer, what's your GC optimization strategy?**

---

**Read `step-01.md`
