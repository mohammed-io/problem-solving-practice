# Step 2: Ensuring Complete Coverage

---

## Span Completion Checklist

**For every service boundary:**

```
[ ] HTTP Client - Wrap with otelhttp
[ ] HTTP Server - Wrap with otelhttp
[ ] gRPC Client - Use otelgrpc
[ ] gRPC Server - Use otelgrpc
[ ] Database queries - Use otelsql
[ ] Message queues - Use instrumentation
[ ] Background jobs - Manually propagate context
```

---

## Detecting Gaps

**Query to find orphaned spans:**

```cypher
// Tempo / Jaeger query
{
  "find": "traces",
  "query": {
    "hasGap": true,
    "duration": "1s+",  // Traces with gaps longer than 1 second
  }
}

// Look for:
// - Time gaps between parent and child spans
// - Spans with no parent (orphaned)
// - Trace ID mismatches
```

**Automated gap detection:**

```python
def trace_has_gaps(trace):
    """Check if trace has unexplained time gaps."""
    spans = trace['spans']
    spans.sort(key=lambda s: s['startTime'])

    for i in range(len(spans) - 1):
        current_end = spans[i]['startTime'] + spans[i]['duration']
        next_start = spans[i + 1]['startTime']

        # Gap larger than 100ms without overlapping spans
        if next_start - current_end > 100_000_000:  # nanoseconds
            gap = next_start - current_end
            print(f"Gap of {gap/1e6:.1f}ms between spans")

            # Check if this gap overlaps with ANY other span
            has_overlap = any(
                s['startTime'] <= current_end <= s['startTime'] + s['duration']
                for s in spans
            )

            if not has_overlap:
                print(f"  UNACCOUNTED GAP - missing span!")
                return True

    return False
```

---

## Background Job Tracing

**Propagate context through goroutines:**

```go
// BAD: Context not propagated
func processOrder(orderID string) {
    go func() {
        // New goroutine - context lost!
        doWork(orderID)
    }()
}

// GOOD: Explicitly pass context
func processOrder(ctx context.Context, orderID string) {
    go func(ctx context.Context) {
        // Context propagated to goroutine
        ctx, span := tracer.Start(ctx, "processOrder")
        defer span.End()

        doWork(ctx, orderID)
    }(ctx)
}
```

**Channel-based work propagation:**

```go
type WorkItem struct {
    Context context.Context
    OrderID string
}

func worker(jobs <-chan WorkItem) {
    for item := range jobs {
        // Use item.Context, not context.Background()
        ctx, span := tracer.Start(item.Context, "worker.process")
        doWork(ctx, item.OrderID)
        span.End()
    }
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's an orphaned span? (A span with no parent, indicates missing trace context propagation)
2. How do you detect gaps in traces? (Look for time gaps between spans that don't overlap with other spans)
3. Why use otelhttp wrapper? (Auto-instruments HTTP client/server with tracing)
4. What's the pattern for goroutine tracing? (Pass context explicitly as function parameter)
5. How do you propagate context through channels? (Include context in WorkItem struct passed through channel)

---

**Continue to `solution.md`
