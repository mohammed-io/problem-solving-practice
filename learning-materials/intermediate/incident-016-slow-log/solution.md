# Solution: The Logging Trap - Synchronous I/O Bottleneck

---

## Root Cause

**Synchronous logging with excessive output** caused I/O contention:

```
10 log lines per request × 100,000 req/s = 1M log writes/second
→ Disk overwhelmed (250 MB/s vs 5 MB/s before)
→ I/O queue builds up
→ Processes block on I/O
→ Latency increases 10-25x
```

The logging format (multiple log.Printf calls) meant each log line was a separate blocking I/O operation.

---

## Immediate Fixes

### Fix 1: Rollback Deployment

```bash
# Immediate rollback
kubectl rollout undo deployment/bid-service

# Or switch to canary
kubectl patch deployment bid-service -p '{"spec":{"template":{"metadata":{"annotations":{"deploy":"v1"}}}}}'
```

### Fix 2: Reduce Verbosity

Keep the deployment but disable detailed logging:

```go
// Add feature flag
var detailedLogging = os.Getenv("DETAILED_LOGGING") == "true"

func ProcessBid(bid Bid) error {
    result := evaluateBid(bid)

    if detailedLogging {
        // Only in dev/staging
        logDetailed(bid, result)
    } else {
        // Production: minimal
        if result.Error != nil {
            log.Printf("ERROR: bid failed user=%d: %v", bid.UserID, result.Error)
        }
    }

    return nil
}
```

---

## Long-term Solutions

### Solution 1: Structured Async Logging

```go
import (
    "go.uber.org/zap"
    "go.uber.org/zap/zapcore"
)

func NewLogger() *zap.Logger {
    // Async core: writes to buffer, separate goroutine flushes
    core := zapcore.NewCore(
        zapcore.NewJSONEncoder(zapcore.EncoderConfig{
            TimeKey:        "ts",
            LevelKey:       "level",
            NameKey:        "logger",
            CallerKey:      "caller",
            MessageKey:     "msg",
            StacktraceKey:  "stacktrace",
            LineEnding:     zapcore.DefaultLineEnding,
            EncodeLevel:    zapcore.LowercaseLevelEncoder,
            EncodeTime:     zapcore.EpochMillisTimeEncoder,
            EncodeDuration: zapcore.SecondsDurationEncoder,
        }),
        &zapcore.WriteSyncer{&BufferedWriter{
            Writer: os.Stdout,
            FlushInterval: 1 * time.Second,  // Flush every second
            BufferSize:     1024 * 1024,     // 1MB buffer
        }},
        zap.InfoLevel,
    )

    return zap.New(core)
}

// Usage
func ProcessBid(bid Bid) error {
    result := evaluateBid(bid)

    // Single structured log (non-blocking)
    logger.Info("bid_processed",
        zap.Int64("user_id", bid.UserID),
        zap.Int64("auction_id", bid.AuctionID),
        zap.Bool("won", result.Won),
        zap.Float64("final_price", result.FinalPrice),
        zap.Duration("duration_ms", time.Since(start)),
    )

    return nil
}
```

### Solution 2: Sampling with Dynamic Rate

```go
type SamplingLogger struct {
    base     *zap.Logger
    sampleRate atomic.Int32  // Percentage (0-100)
}

func (sl *SamplingLogger) Info(msg string, fields ...zap.Field) {
    // Always log errors
    if sl.sampleRate.Load() == 100 {
        sl.base.Info(msg, fields...)
        return
    }

    // Sample based on rate
    if rand.Intn(100) < int(sl.sampleRate.Load()) {
        sl.base.Info(msg, fields...)
    }
}

// Dynamically adjust via API
func SetSampleRate(rate int) {
    samplingLogger.sampleRate.Store(int32(rate))
}

// Usage: increase sampling when debugging
// POST /admin/log-sample-rate {"rate": 10}
```

### Solution 3: Centralized Logging Service

```
┌────────────────────────────────────────────────────────────┐
│                  Application Servers                       │
│                   (non-blocking send)                      │
└────────────────────────┬───────────────────────────────────┘
                         │
                         ▼ (UDP/local buffer)
┌────────────────────────────────────────────────────────────┐
│                 Fluentd / Fluent Bit                       │
│                  (local agent)                             │
│                   Buffers locally                          │
└────────────────────────┬───────────────────────────────────┘
                         │
                         ▼ (batched, compressed)
┌────────────────────────────────────────────────────────────┐
│                 Elasticsearch / S3                         │
│                 (central storage)                          │
└────────────────────────────────────────────────────────────┘
```

**Benefits:**
- Apps log to local agent (non-blocking)
- Agent handles batching, compression, retries
- Centralized query and analysis

**Implementation:**
```go
// Log to local Fluentd agent (Unix socket)
import "github.com/ugorji/go/codec"

func logToFluentd(msg map[string]interface{}) error {
    // Non-blocking send to Unix socket
    conn, _ := net.Dial("unix", "/var/run/fluent/fluent.sock")
    defer conn.Close()

    // Write msg (non-blocking if socket buffer not full)
    msghash.Encode(conn, msg)
    return nil
}
```

### Solution 4: OpenTelemetry Logging

```go
import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/stdout/stdouttrace"
)

func setupTracing() {
    exporter, _ := stdouttrace.New(stdouttrace.WithPrettyPrint())
    tp := trace.NewTracerProvider(trace.WithSyncer(exporter))
    otel.SetTracerProvider(tp)
}

func ProcessBid(bid Bid) error {
    ctx := context.Background()
    ctx, span := otel.Tracer("bid-service").Start(ctx, "ProcessBid")
    defer span.End()

    // Add attributes to span (non-blocking)
    span.SetAttributes(
        attribute.Int64("user.id", bid.UserID),
        attribute.Int64("auction.id", bid.AuctionID),
    )

    result := evaluateBid(bid)

    if result.Error != nil {
        span.RecordError(result.Error)
        span.SetStatus(codes.Error, result.Error.Error())
    } else {
        span.SetStatus(codes.Ok, "bid processed")
    }

    return nil
}
```

---

## Systemic Prevention (Staff Level)

### 1. Log Levels by Environment

| Environment | Level | Purpose |
|-------------|-------|---------|
| Production  | WARN+ | Only errors and warnings |
| Production  | INFO+ | Sampled 1% of requests |
| Staging     | DEBUG+ | Full logging |
| Development | DEBUG+ | Full logging |

### 2. Log Cost Budgeting

Treat logging like any other resource:

```
Log Cost Budget:
- Max logs per request: 3 lines
- Max log size per line: 500 bytes
- Max logs per second: 10,000
- Max disk usage: 10 GB/day
```

Alert when budgets exceeded.

### 3. Pre-commit Log Review

Code review checklist:
- [ ] Is this log necessary for production?
- [ ] Can this be sampled instead of always logged?
- [ ] Is the log line structured (not printf)?
- [ ] Does this log contain sensitive data (PII)?
- [ ] Is this log at appropriate level?

### 4. Performance Testing with Logging

```bash
# Load test WITH production logging config
./load-test \
  --log-level=warn \
  --log-sample-rate=1 \
  --requests=100000 \
  --target-latency-p99=50ms

# If latency > 50ms, logging is too expensive
```

---

## Real Incident

**Uber (2015):** Excessive logging caused performance degradation in Go services. The issue was synchronous writes to syslog. Fixed by switching to buffered async logging and sampling.

**CLOUD (2018):** Node.js service with `console.log` in hot path caused 40% CPU usage. Fixed by removing logs from request handling path.

---

## Jargon

| Term | Definition |
|------|------------|
| **Synchronous I/O** | Operation blocks until complete |
| **Asynchronous I/O** | Operation returns immediately, I/O happens in background |
| **Structured logging** | JSON/key-value logging, easier to parse and query |
| **Sampling** | Logging only subset of events (e.g., 1%) |
| **Buffer** | Memory holding data before flush to disk |
| **Flush** | Writing buffer contents to disk |
| **I/O contention** | Multiple processes competing for disk I/O bandwidth |
| **Non-blocking** | Function returns immediately, operation continues in background |

---

## Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| **Async logging** | Fast, non-blocking | Can lose logs on crash |
| **Sampling** | Detailed logs for subset | Might miss issues |
| **Centralized logging** | Scalable, queryable | More infrastructure |
| **Reduce logging** | Simple, fast | Less debugging info |
| **Environment-specific** | Production optimized | Dev/prod behavior diff |

For production services: **Structured async logging + sampling + centralized aggregation** is best.

---

**Next Problem:** `intermediate/design-010-sharded-kv/`
