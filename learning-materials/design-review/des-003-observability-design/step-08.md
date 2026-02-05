# Step 08: Structured Logging

---

## The Problem

The team's logs are **unstructured text**:

```
❌ Current logs:
[2024-01-15 14:32:01] OrderService: Processing order
[2024-01-15 14:32:02] OrderService: Got request
[2024-01-15 14:32:03] PaymentService: Payment failed
[2024-01-15 14:32:04] ERROR: Something went wrong

Problems:
- Can't query: "Show me all failed payments for order-123"
- No correlation between services
- grep-ing is painful
- Can't aggregate/analyze
```

---

## Solution: Structured Logging

**Structured logs** = machine-readable logs with fields.

```
✅ Structured logs:
{
  "timestamp": "2024-01-15T14:32:01Z",
  "level": "info",
  "service": "order-service",
  "trace_id": "abc123",
  "span_id": "def456",
  "event": "order.created",
  "order_id": "123",
  "user_id": "456",
  "total": 99.99
}

Now you can:
- Query: event="order.created" AND order_id="123"
- Correlate: trace_id="abc123" across all services
- Aggregate: count by event, service
```

---

## Structured Logging in Go

```go
package logging

import (
    "context"
    "go.opentelemetry.io/otel/trace"
    "go.uber.org/zap"
    "go.uber.org/zap/zapcore"
)

type Logger struct {
    zap *zap.Logger
}

func NewLogger(serviceName string) *Logger {
    config := zap.NewProductionConfig()
    config.EncoderConfig.TimeKey = "timestamp"
    config.EncoderConfig.EncodeTime = zapcore.ISO8601TimeEncoder

    logger, _ := config.Build()
    logger = logger.With(zap.String("service", serviceName))

    return &Logger{zap: logger}
}

// Inject trace context into all logs
func (l *Logger) WithTrace(ctx context.Context) *zap.Logger {
    spanContext := trace.SpanFromContext(ctx).SpanContext()

    fields := []zap.Field{}
    if spanContext.IsValid() {
        fields = append(fields,
            zap.String("trace_id", spanContext.TraceID().String()),
            zap.String("span_id", spanContext.SpanID().String()),
        )
    }

    return l.zap.With(fields...)
}

func (l *Logger) Info(ctx context.Context, msg string, fields ...zap.Field) {
    l.WithTrace(ctx).Info(msg, fields...)
}

func (l *Logger) Error(ctx context.Context, msg string, fields ...zap.Field) {
    l.WithTrace(ctx).Error(msg, fields...)
}

// Usage
func (h *OrderHandler) CreateOrder(w http.ResponseWriter, r *http.Request) {
    h.logger.Info(r.Context(), "handling_create_order",
        zap.String("user_id", getUserID(r)),
        zap.Float64("total", getOrderTotal(r)),
    )

    order, err := h.service.CreateOrder(r.Context(), req)
    if err != nil {
        h.logger.Error(r.Context(), "failed_to_create_order",
            zap.Error(err),
            zap.String("user_id", getUserID(r)),
        )
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }

    h.logger.Info(r.Context(), "order_created",
        zap.String("order_id", order.ID),
        zap.String("user_id", order.UserID),
    )
}
```

---

## Log Levels

Use levels consistently:

| Level | When to Use | Example |
|-------|-------------|---------|
| **DEBUG** | Detailed diagnostics | "Cache miss for key: order-123" |
| **INFO** | Normal operations | "Order created: order-123" |
| **WARN** | Something unexpected but not error | "High latency: 500ms (normally 100ms)" |
| **ERROR** | Error that was handled | "Payment declined: card expired" |
| **FATAL** | Service cannot continue | "Cannot connect to database, exiting" |

**Rule:** Log at the **lowest level that captures the information**.

---

## Log Aggregation Query Examples

With structured logs, you can query like a database:

```
# Find all logs for a specific request
trace_id:"abc123"

# Find all errors in last hour
level:"error" AND @timestamp:[now-1h TO now]

# Find all failed payments
event:"payment.failed"

# Find slow requests
duration_ms:>1000

# Find orders for a user
event:"order.created" AND user_id:"456"

# Aggregate by service
{service:"*"} | stats count() by service
```

---

## Quick Check

Before moving on, make sure you understand:

1. What is structured logging? (Machine-readable, field-based)
2. Why include trace_id in logs? (Correlate across services)
3. When should you log at ERROR vs INFO? (Handled errors vs normal operations)
4. What can you do with structured logs that you can't with text logs? (Query, aggregate, correlate)

---

**Ready to build dashboards? Read `step-09.md`**
