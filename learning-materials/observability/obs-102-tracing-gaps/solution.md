# Solution: Complete Distributed Tracing

---

## Root Cause

**Three issues caused missing spans:**
1. HTTP client not injecting trace context
2. Server not extracting trace context
3. No spans around blocking operations

---

## Complete Solution

### 1. Auto-Instrumentation

```go
package main

import (
    "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/propagation"
)

func init() {
    // Set global propagator
    otel.SetTextMapPropagator(propagation.TraceContext{})
}

// HTTP Client with auto-tracing
func NewTracedClient() *http.Client {
    return &http.Client{
        Transport: otelhttp.NewTransport(http.DefaultTransport),
    }
}

// HTTP Server middleware
func TracingMiddleware(next http.Handler) http.Handler {
    return otelhttp.NewHandler(next, "http")
}
```

### 2. Complete Handler Example

```go
package handlers

import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/trace"
)

type OrderHandler struct {
    orderClient    *OrderClient
    client         *http.Client
    tracer         trace.Tracer
}

func NewOrderHandler() *OrderHandler {
    return &OrderHandler{
        client: NewTracedClient(),
        tracer: otel.Tracer("order"),
    }
}

func (h *OrderHandler) HandleOrder(w http.ResponseWriter, r *http.Request) {
    ctx, span := h.tracer.Start(r.Context(), "HandleOrder")
    defer span.End()

    // All downstream calls automatically propagate context
    order, err := h.orderClient.GetOrder(ctx, orderID)
    if err != nil {
        span.RecordError(err)
        return
    }

    json.NewEncoder(w).Encode(order)
}

func (c *OrderClient) GetOrder(ctx context.Context, id string) (*Order, error) {
    ctx, span := c.tracer.Start(ctx, "OrderClient.GetOrder")
    defer span.End()

    req, _ := http.NewRequestWithContext(ctx, "GET", c.url+"/orders/"+id, nil)

    // traceparent header injected automatically by otelhttp transport
    resp, err := c.client.Do(req)
    if err != nil {
        span.RecordError(err)
        return nil, err
    }
    defer resp.Body.Close()

    var order Order
    json.NewDecoder(resp.Body).Decode(&order)
    return &order, nil
}
```

### 3. Coverage Verification

**Integration test for tracing:**

```go
func TestTracingCoverage(t *testing.T) {
    // Exporter that captures spans in memory
    exporter := &inMemoryExporter{}
    tp := tracesdk.NewTracerProvider(
        tracesdk.WithSyncer(exporter),
    )
    otel.SetTracerProvider(tp)

    // Make request through full stack
    resp := makeRequest(t, "GET /api/orders/123")

    assert.Equal(t, 200, resp.StatusCode)

    // Verify all expected spans present
    spans := exporter.GetSpans()
    spanNames := map[string]bool{}
    for _, span := range spans {
        spanNames[span.Name] = true
    }

    expectedSpans := []string{
        "HandleOrder",
        "OrderClient.GetOrder",
        "HTTP GET",  // HTTP client span
    }

    for _, expected := range expectedSpans {
        assert.True(t, spanNames[expected],
            "Missing span: %s", expected)
    }

    // Verify trace continuity
    traceIDs := map[string]bool{}
    for _, span := range spans {
        traceIDs[span.SpanContext.TraceID().String()] = true
    }

    // All spans should have same trace ID
    assert.Equal(t, 1, len(traceIDs),
        "Spans have different trace IDs!")
}
```

### 4. Gap Detection Alert

```yaml
# Observability alert
groups:
  - name: tracing_gaps
    rules:
      - alert: TraceGapDetected
        expr: |
          (
            sum(rate(traces_span_duration_seconds_sum{service="api"}[5m]))
            - sum(rate(traces_span_duration_seconds_sum{service="api",child="true"}[5m]))
          ) > 0
        annotations:
          summary: "Time gaps detected in traces"
```

---

## Quick Checklist

**For each service:**
- [ ] Auto-instrument HTTP client (otelhttp)
- [ ] Auto-instrument HTTP server (middleware)
- [ ] Verify traceparent header propagation
- [ ] Add spans around blocking operations
- [ ] Test trace continuity end-to-end
- [ ] Monitor for orphaned spans

**For background jobs:**
- [ ] Pass context explicitly to goroutines
- [ ] Use context-aware work queues
- [ ] Add spans at job boundaries

---

**Next Problem:** `observability/obs-103-slo-calculation/`
