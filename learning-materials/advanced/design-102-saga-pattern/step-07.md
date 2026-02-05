# Step 07: Production Concerns

---

## The Challenge

Your saga works in dev. Now you need to make it production-ready.

```
Production concerns:
❌ Duplicate events (network retries cause double-processing)
❌ Events lost (service crashes before persisting)
❌ Can't trace request across services
❌ No audit trail for compliance
```

---

## Concern 1: Idempotency

**Problem:** Network retries can cause duplicate events.

```
Payment service publishes PaymentCharged event:
  Attempt 1: Network timeout → retry
  Attempt 2: Succeeds!

Inventory service receives:
  - PaymentCharged event (twice!)
  - Reserves inventory twice → out of stock!
```

**Solution: Idempotency Keys**

```go
type IdempotencyHandler struct {
    processedLog ProcessedLogRepository
}

func (h *IdempotencyHandler) HandleEvent(ctx context.Context, event OrderCreatedEvent) error {
    // Use correlation ID as idempotency key
    idempotencyKey := event.CorrelationID

    // Check if already processed
    exists, err := h.processedLog.Exists(ctx, idempotencyKey)
    if err != nil {
        return err
    }
    if exists {
        return nil // Skip duplicate
    }

    // Process the event
    if err := h.processOrder(ctx, event); err != nil {
        return err
    }

    // Mark as processed
    return h.processedLog.Mark(ctx, idempotencyKey)
}

// Storage for idempotency keys
CREATE TABLE processed_log (
    idempotency_key VARCHAR(200) PRIMARY KEY,
    processed_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '7 days'
);

-- Auto-cleanup old entries (or use TTL)
```

---

## Concern 2: Transactional Outbox

**Problem:** Service crashes between writing to DB and publishing event.

```
1. Service writes order to DB: ✓
2. Service publishes OrderCreated event
3. Service crashes before publish completes!

Result: Order exists but no one knows → orphaned order
```

**Solution: Atomic write of domain change + event**

```sql
-- Atomic write using database transaction
BEGIN;

INSERT INTO orders (id, customer_id, total) VALUES ('123', '456', 99.99);
INSERT INTO outbox (id, aggregate_id, event_type, payload)
    VALUES (uuid(), '123', 'OrderCreated', '{"order_id":"123"}');

COMMIT;

-- Either both succeed or both fail
```

```go
func (s *OrderService) CreateOrder(ctx context.Context, req CreateOrderRequest) error {
    return s.repo.WithTransaction(ctx, func(tx Tx) error {
        // 1. Create order
        order := &Order{
            ID:         generateID(),
            CustomerID: req.CustomerID,
            Total:      req.Total,
        }

        if err := tx.Orders().Create(ctx, order); err != nil {
            return err
        }

        // 2. Write to outbox (same transaction)
        event := OutboxMessage{
            AggregateID: order.ID,
            EventType:   "OrderCreated",
            Payload:     json.Marshal(map[string]string{"order_id": order.ID}),
        }

        if err := tx.Outbox().Create(ctx, event); err != nil {
            return err
        }

        return nil
    })
}

// Background worker publishes outbox events
func (w *OutboxWorker) Run(ctx context.Context) {
    ticker := time.NewTicker(1 * time.Second)
    defer ticker.Stop()

    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            messages := w.outboxRepo.GetUnpublished(ctx, 100)

            for _, msg := range messages {
                if err := w.eventBus.Publish(msg.EventType, msg.Payload); err != nil {
                    continue // Will retry next tick
                }

                w.outboxRepo.MarkPublished(ctx, msg.ID)
            }
        }
    }
}
```

---

## Concern 3: Correlation IDs

**Problem:** Can't trace a request across multiple services.

```
User: "Where's my order?"
You: "Let me check the logs..."
  - Order service log: "Order created"
  - Payment service log: "Payment charged"
  - But which payment corresponds to which order?
```

**Solution: Correlation ID propagated through all events**

```go
package tracing

import (
    "context"
    "github.com/google/uuid"
)

type contextKey string

const CorrelationIDKey contextKey = "correlation_id"

func WithCorrelationID(ctx context.Context, id string) context.Context {
    return context.WithValue(ctx, CorrelationIDKey, id)
}

func GetCorrelationID(ctx context.Context) string {
    if id, ok := ctx.Value(CorrelationIDKey).(string); ok {
        return id
    }
    return uuid.New().String() // Generate if not present
}

// Usage in HTTP handler
func (h *OrderHandler) CreateOrder(w http.ResponseWriter, r *http.Request) {
    correlationID := r.Header.Get("X-Correlation-ID")
    if correlationID == "" {
        correlationID = uuid.New().String()
    }

    ctx := WithCorrelationID(r.Context(), correlationID)

    // All logs include correlation ID
    h.logger.Info(ctx, "creating_order",
        zap.String("correlation_id", correlationID),
        zap.String("customer_id", req.CustomerID),
    )

    order, err := h.service.CreateOrder(ctx, req)

    // Publish event with correlation ID
    event := OrderCreatedEvent{
        OrderID:       order.ID,
        CorrelationID: correlationID,
        CustomerID:    req.CustomerID,
    }

    h.eventBus.Publish("order.created", event)
}

// Payment service receives event with correlation ID
func (s *PaymentService) HandleOrderCreated(ctx context.Context, event OrderCreatedEvent) error {
    // Extract correlation ID from event
    ctx = WithCorrelationID(ctx, event.CorrelationID)

    s.logger.Info(ctx, "processing_payment",
        zap.String("correlation_id", event.CorrelationID),
        zap.String("order_id", event.OrderID),
    )

    // Now logs are correlated across services!
}
```

---

## Production Checklist

```
Before deploying to production:

[ ] All events have correlation IDs
[ ] Event handlers are idempotent
[ ] Outbox pattern implemented for event publishing
[ ] Saga log persisted after each step
[ ] Dead letter queue for failed compensation
[ ] Recovery logic tested (kill orchestrator mid-saga)
[ ] Distributed tracing instrumentation
[ ] Metrics for saga health (success rate, compensation rate)
[ ] Runbooks for common failure scenarios
[ ] Alerting for stuck sagas
```

---

## Quick Check

Before moving on, make sure you understand:

1. Why use idempotency keys? (Handle duplicate events)
2. What is the transactional outbox? (Atomic DB + event write)
3. Why propagate correlation IDs? (Trace request across services)
4. What's in the production checklist? (All of the above)

---

**Ready for the complete solution? Read `solution.md`**
