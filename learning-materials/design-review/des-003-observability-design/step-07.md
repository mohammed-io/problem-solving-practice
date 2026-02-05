# Step 07: Distributed Tracing Implementation

---

## The Problem

You have metrics and logs, but you still can't answer:

```
User: "My order #123 is slow, why?"
You: "Let me check..."
  - Metrics show: "p95 latency is 200ms" ✓ (system is fine)
  - Logs show: "OrderService processed order-123" ✓ (no errors)
  - But WHERE did it spend time? Which service was slow?

❌ Without tracing: You're flying blind across service boundaries
```

---

## What is a Trace?

A trace is a **tree of spans** representing one request's journey:

```
GET /api/orders/123

┌─────────────────────────────────────────────────────────────┐
│  Span 1: API Gateway (total: 847ms)                         │
│  ├─ Span 2: Auth Service (45ms)                             │
│  │   └─ Validated token for user-12345                      │
│  ├─ Span 3: Order Service (795ms) ⚠️ SLOW                   │
│  │   ├─ Span 3.1: Cache lookup (5ms) - MISS                 │
│  │   └─ Span 3.2: Database query (785ms) ⚠️ VERY SLOW       │
│  │       └─ SELECT * FROM orders WHERE id = '123'          │
│  │       └─ Full table scan! No index on id                 │
│  └─ Span 4: Inventory Service (15ms)                        │
│      └─ Reserved item-456                                    │
└─────────────────────────────────────────────────────────────┘

💡 Insight: Database query is the bottleneck (785ms of 847ms total)
```

---

## OpenTelemetry in Go

```go
package main

import (
    "context"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/jaeger"
    "go.opentelemetry.io/otel/sdk/resource"
    tracesdk "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/otel/semconv/v1.4.0"
    "go.opentelemetry.io/otel/trace"
)

func InitTracer(serviceName string) (trace.Tracer, error) {
    // Create Jaeger exporter
    exp, err := jaeger.New(jaeger.WithCollectorEndpoint(
        jaeger.WithEndpoint("http://jaeger:14268/api/traces"),
    ))
    if err != nil {
        return nil, err
    }

    // Create tracer provider
    tp := tracesdk.NewTracerProvider(
        tracesdk.WithBatcher(exp),
        tracesdk.WithResource(resource.NewWithAttributes(
            semconv.SchemaURL,
            semconv.ServiceNameKey.String(serviceName),
        )),
    )

    otel.SetTracerProvider(tp)

    return tp.Tracer(serviceName), nil
}

// Usage in HTTP handler
func (h *OrderHandler) GetOrders(w http.ResponseWriter, r *http.Request) {
    // Start span
    ctx, span := h.tracer.Start(r.Context(), "GetOrders")
    defer span.End()

    // Add attributes (metadata)
    orderID := r.PathValue("id")
    span.SetAttributes(
        attribute.String("order.id", orderID),
        attribute.String("user.id", getUserID(ctx)),
    )

    // Do work
    orders, err := h.service.GetOrders(ctx, orderID)
    if err != nil {
        // Record error
        span.RecordError(err)
        span.SetStatus(codes.Error, "failed to get orders")
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }

    span.SetStatus(codes.Ok, "success")
    json.NewEncoder(w).Encode(orders)
}
```

---

## Propagating Trace Context

The key to distributed tracing is **context propagation**:

```go
// Client makes request with trace context
func (c *OrderClient) GetOrder(ctx context.Context, orderID string) (*Order, error) {
    // Start child span
    ctx, span := c.tracer.Start(ctx, "OrderClient.GetOrder")
    defer span.End()

    // HTTP request automatically includes trace headers
    req, _ := http.NewRequestWithContext(ctx, "GET",
        "http://order-service/orders/"+orderID, nil)

    // Headers automatically injected:
    // traceparent: 00-abc123...-def456...-01
    // tracestate: rojo=00f067aa0ba902b7

    resp, err := c.httpClient.Do(req)
    // Trace continues in OrderService automatically
    return parseResponse(resp)
}
```

---

## What to Trace?

| Decision | Trace? | Reason |
|----------|--------|--------|
| **HTTP requests** | ✅ Yes | Entry point for most user requests |
| **Database queries** | ✅ Yes | Often the bottleneck |
| **External API calls** | ✅ Yes | Can be slow, not your control |
| **Cache lookups** | ⚠️ Maybe | Only if slow (miss vs hit) |
| **Background jobs** | ✅ Yes | Need visibility into async work |
| **Health checks** | ❌ No | Too noisy, not useful |

**Rule of thumb:** Trace anything that crosses a network or process boundary.

---

## Quick Check

Before moving on, make sure you understand:

1. What is a span? (A single operation in a trace)
2. What is a trace? (A tree of spans representing one request)
3. Why propagate context? (Connect spans across services)
4. What should you trace? (Network boundaries, slow operations)

---

**Ready to add structured logging? Read `step-08.md`**
