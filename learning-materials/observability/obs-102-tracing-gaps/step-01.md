# Step 1: Trace Context Propagation

---

## The traceparent Header

**W3C Trace Context format:**

```
traceparent: 00-{trace_id}-{span_id}-{trace_flags}

Example:
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01

Breakdown:
  00                    - Version
  4bf92f...4736         - Trace ID (16 bytes, 32 hex chars)
  00f067...02b7         - Span ID (8 bytes, 16 hex chars)
  01                    - Flags (01 = sampled)
```

**Injecting context (outgoing):**

```go
import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/propagation"
    "net/http"
)

var propagator = propagation.TraceContext{}

func (c *OrderClient) GetOrder(ctx context.Context, id string) (*Order, error) {
    req, _ := http.NewRequestWithContext(ctx, "GET", c.url+"/orders/"+id, nil)

    // CRITICAL: Inject trace context into HTTP headers
    propagator.Inject(ctx, propagation.HeaderCarrier(req.Header))

    // Result: traceparent header added automatically
    // traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01

    return c.client.Do(req)
}
```

**Extracting context (incoming):**

```go
import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/trace"
)

func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    // CRITICAL: Extract trace context from incoming request
    propagator := propagation.TraceContext{}
    ctx := propagator.Extract(r.Context(), propagation.HeaderCarrier(r.Header))

    // Continue trace instead of starting new one
    ctx, span := tracer.Start(
        ctx,  // Use extracted context, NOT context.Background()!
        "GetOrder",
    )
    defer span.End()

    // This span is now part of the existing trace
}
```

---

## Baggage vs Trace Context

**Trace Context (traceparent):**
- Propagates trace ID, span ID, sampling flags
- Required for trace continuation
- Small, fixed size

**Baggage (baggage header):**
- Propagates user-defined key-value pairs
- Optional, for additional context
- Can grow large

```
Request Headers:
  traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
  baggage: user_id=12345,tenant=acme,customer_tier=premium
```

```go
// Setting baggage
func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    ctx := baggage.ContextWithBaggage(r.Context(),
        baggage.FromContext(ctx).SetMember("user_id", "12345"),
    )
    // baggage automatically propagated with subsequent calls
}
```

---

## HTTP Client Wrapper

**Auto-instrumented HTTP client:**

```go
package httptrace

import (
    "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
    "net/http"
)

// Wrapper that automatically adds spans and propagates context
func NewClient(base *http.Client) *http.Client {
    transport := otelhttp.NewTransport(base.Transport)
    return &http.Client{
        Transport: transport,
        Timeout:   base.Timeout,
    }
}

// Usage
client = httptrace.NewClient(http.DefaultClient)

// All requests through this client automatically:
// 1. Create child span
// 2. Inject traceparent header
// 3. Propagate baggage
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's the traceparent header format? (00-{trace_id}-{span_id}-{trace_flags})
2. How long is a trace ID? (16 bytes = 32 hex characters)
3. What's the difference between traceparent and baggage? (traceparent = trace ID/span ID/flags, baggage = user key-value pairs)
4. Why use extracted context instead of context.Background()? (Continues existing trace instead of starting new one)
5. What does otelhttp.NewTransport do? (Auto-instruments HTTP client with tracing)

---

**Continue to `step-02.md`
