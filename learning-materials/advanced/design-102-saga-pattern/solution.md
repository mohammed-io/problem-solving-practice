---
name: design-102-saga-pattern
description: Distributed transactions using Saga pattern - choreography, orchestration, and compensation
difficulty: Advanced
category: Distributed Systems
level: Principal Engineer
---

# Solution: Saga Pattern for Distributed Transactions

---

## Answers

### 1. Ensuring Consistency Without Distributed Transactions

**Use Sagas with Compensating Transactions:**

A saga is a sequence of local transactions. Each local transaction updates data within a single service. If a step fails, compensating transactions undo the effects of previous steps.

**Key principles:**
- Each service owns its data
- No distributed locks
- No two-phase commit
- Eventual consistency is acceptable
- Compensation is always possible

### 2. Payment Succeeds, Inventory Fails

**Execute compensating transactions in reverse order:**

1. Inventory failed → skip (nothing to compensate)
2. Payment succeeded → refund payment
3. Order created → cancel order

The system ends in a consistent state where the customer is not charged and the order is cancelled.

### 3. Handling Compensation

**Compensation must be idempotent and reliable:**

```go
package saga

import (
    "context"
    "fmt"
)

type PaymentService struct {
    repo    PaymentRepository
    gateway PaymentGateway
}

func (s *PaymentService) ChargePayment(ctx context.Context, orderID string, amount float64) (string, error) {
    // Store payment_id for compensation
    payment := &Payment{
        ID:      generateID(),
        OrderID: orderID,
        Amount:  amount,
        Status:  "charged",
    }

    if err := s.repo.Create(ctx, payment); err != nil {
        return "", err
    }

    return payment.ID, nil
}

func (s *PaymentService) RefundPayment(ctx context.Context, paymentID string) error {
    // Idempotent refund
    payment, err := s.repo.GetByID(ctx, paymentID)
    if err != nil {
        return err
    }

    // Check if already refunded
    if payment.Status == "refunded" {
        return nil // Already refunded, still success
    }

    // Update and refund
    payment.Status = "refunded"
    if err := s.repo.Update(ctx, payment); err != nil {
        return err
    }

    return s.gateway.Refund(payment.ChargeID)
}
```

**Each compensating transaction:**
- Takes the original request ID
- Checks if already compensated
- Records the compensation
- Is retryable

### 4. Choreography vs Orchestration

| Aspect | Choreography | Orchestration |
|--------|-------------|---------------|
| **Coordination** | Decentralized (events) | Central (orchestrator) |
| **Complexity** | Workflow logic spread out | Workflow logic in one place |
| **Coupling** | Loose (event-driven) | Tight (orchestrator knows all) |
| **Debugging** | Hard (distributed logic) | Easier (central state) |
| **Failure** | No SPOF | Orchestrator is SPOF |
| **Best for** | Simple workflows, high scale | Complex workflows, audit needs |

### 5. Saga Design for Order Flow

**Orchestration-based saga (recommended for order flows):**

```go
package saga

import (
    "context"
    "fmt"
    "time"
)

type SagaState string

const (
    SagaStateStarted      SagaState = "STARTED"
    SagaStateCompleted    SagaState = "COMPLETED"
    SagaStateFailed       SagaState = "FAILED"
    SagaStateCompensating SagaState = "COMPENSATING"
    SagaStateCompensated  SagaState = "COMPENSATED"
)

type OrderSaga struct {
    orderID     string
    state       SagaState
    steps       []string
    completed   []string
    paymentID   string
    orderRepo   OrderRepository
    paymentSvc  PaymentServiceClient
    inventorySvc InventoryServiceClient
}

func NewOrderSaga(orderID string, deps Deps) *OrderSaga {
    return &OrderSaga{
        orderID:     orderID,
        state:       SagaStateStarted,
        steps:       []string{"create_order", "charge_payment", "reserve_inventory", "confirm_order"},
        completed:   make([]string, 0),
        orderRepo:   deps.OrderRepo,
        paymentSvc:  deps.PaymentSvc,
        inventorySvc: deps.InventorySvc,
    }
}

func (s *OrderSaga) Execute(ctx context.Context, req CreateOrderRequest) error {
    var err error

    // Step 1: Create Order
    order, err := s.createOrder(ctx, req)
    if err != nil {
        return fmt.Errorf("create order: %w", err)
    }
    s.completed = append(s.completed, "create_order")

    // Step 2: Charge Payment
    paymentID, err := s.chargePayment(ctx, order)
    if err != nil {
        _ = s.compensate(ctx)
        return fmt.Errorf("charge payment: %w", err)
    }
    s.paymentID = paymentID
    s.completed = append(s.completed, "charge_payment")

    // Step 3: Reserve Inventory
    if err := s.reserveInventory(ctx, order); err != nil {
        _ = s.compensate(ctx)
        return fmt.Errorf("reserve inventory: %w", err)
    }
    s.completed = append(s.completed, "reserve_inventory")

    // Step 4: Confirm Order
    if err := s.confirmOrder(ctx, order); err != nil {
        _ = s.compensate(ctx)
        return fmt.Errorf("confirm order: %w", err)
    }
    s.completed = append(s.completed, "confirm_order")

    s.state = SagaStateCompleted
    return nil
}

func (s *OrderSaga) compensate(ctx context.Context) error {
    s.state = SagaStateCompensating

    // Compensate in reverse order
    for i := len(s.completed) - 1; i >= 0; i-- {
        step := s.completed[i]

        switch step {
        case "confirm_order":
            _ = s.unconfirmOrder(ctx)
        case "reserve_inventory":
            _ = s.releaseInventory(ctx)
        case "charge_payment":
            _ = s.refundPayment(ctx, s.paymentID)
        case "create_order":
            _ = s.cancelOrder(ctx)
        }
    }

    s.state = SagaStateCompensated
    return nil
}

func (s *OrderSaga) createOrder(ctx context.Context, req CreateOrderRequest) (*Order, error) {
    order := &Order{
        ID:         s.orderID,
        CustomerID: req.CustomerID,
        Total:      req.Total,
        Status:     "pending",
    }
    return order, s.orderRepo.Create(ctx, order)
}

func (s *OrderSaga) chargePayment(ctx context.Context, order *Order) (string, error) {
    return s.paymentSvc.ChargePayment(ctx, order.ID, order.Total)
}

func (s *OrderSaga) reserveInventory(ctx context.Context, order *Order) error {
    return s.inventorySvc.ReserveInventory(ctx, order.ID)
}

func (s *OrderSaga) confirmOrder(ctx context.Context, order *Order) error {
    order.Status = "confirmed"
    return s.orderRepo.Update(ctx, order)
}

func (s *OrderSaga) refundPayment(ctx context.Context, paymentID string) error {
    return s.paymentSvc.RefundPayment(ctx, paymentID)
}

func (s *OrderSaga) cancelOrder(ctx context.Context) error {
    return s.orderRepo.Cancel(ctx, s.orderID)
}

func (s *OrderSaga) releaseInventory(ctx context.Context) error {
    return s.inventorySvc.ReleaseReservation(ctx, s.orderID)
}

func (s *OrderSaga) unconfirmOrder(ctx context.Context) error {
    // Unconfirm is essentially setting status back to pending
    order, _ := s.orderRepo.GetByID(ctx, s.orderID)
    order.Status = "cancelled"
    return s.orderRepo.Update(ctx, order)
}
```

---

## Best Practices

### 1. Transactional Outbox

```sql
-- Atomic write of domain change and event
BEGIN;
INSERT INTO orders (id, customer_id, total) VALUES (123, 456, 100.00);
INSERT INTO outbox (aggregate_id, event_type, payload) VALUES (123, 'OrderCreated', '{"order_id":123}');
COMMIT;
```

```go
package outbox

import (
    "context"
    "encoding/json"
    "time"
)

type OutboxMessage struct {
    ID         int64     `json:"id"`
    AggregateID string   `json:"aggregate_id"`
    EventType   string   `json:"event_type"`
    Payload     json.RawMessage `json:"payload"`
    Status      string   `json:"status"`
    CreatedAt   time.Time `json:"created_at"`
    ProcessedAt *time.Time `json:"processed_at,omitempty"`
}

type OutboxRepository interface {
    Store(ctx context.Context, msg *OutboxMessage) error
    GetUnprocessed(ctx context.Context, limit int) ([]*OutboxMessage, error)
    MarkProcessed(ctx context.Context, id int64) error
}

// Usage in transaction
func (s *OrderService) CreateOrder(ctx context.Context, req CreateOrderRequest) error {
    return s.repo.WithTransaction(ctx, func(tx Tx) error {
        order := &Order{
            ID:         generateID(),
            CustomerID: req.CustomerID,
            Total:      req.Total,
        }

        if err := tx.Orders().Create(ctx, order); err != nil {
            return err
        }

        // Store event in outbox (same transaction)
        payload, _ := json.Marshal(map[string]string{"order_id": order.ID})
        return tx.Outbox().Store(ctx, &OutboxMessage{
            AggregateID: order.ID,
            EventType:   "OrderCreated",
            Payload:     payload,
            Status:      "pending",
        })
    })
}
```

### 2. Idempotency Keys

```go
package idempotency

import (
    "context"
    "crypto/sha256"
    "encoding/hex"
    "time"
)

type IdempotencyRepository interface {
    GetResult(ctx context.Context, key string) (*CachedResult, error)
    StoreResult(ctx context.Context, key string, result interface{}, ttl time.Duration) error
}

type CachedResult struct {
    Response interface{} `json:"response"`
    StoredAt time.Time   `json:"stored_at"`
}

type IdempotencyMiddleware struct {
    repo IdempotencyRepository
    ttl  time.Duration
}

func (m *IdempotencyMiddleware) Process(ctx context.Context, key string, fn func() (interface{}, error)) (interface{}, error) {
    // Check if already processed
    if cached, err := m.repo.GetResult(ctx, key); err == nil && cached != nil {
        return cached.Response, nil // Return cached result
    }

    // Execute the function
    result, err := fn()
    if err != nil {
        return nil, err
    }

    // Store result for future requests
    _ = m.repo.StoreResult(ctx, key, result, m.ttl)

    return result, nil
}

// Usage in HTTP handler
func (h *OrderHandler) CreateOrder(w http.ResponseWriter, r *http.Request) {
    // Extract idempotency key from header
    idempotencyKey := r.Header.Get("X-Idempotency-Key")
    if idempotencyKey == "" {
        http.Error(w, "Missing idempotency key", http.StatusBadRequest)
        return
    }

    // Hash the key for storage
    hash := sha256.Sum256([]byte(idempotencyKey))
    key := hex.EncodeToString(hash[:])

    result, err := h.idempotency.Process(r.Context(), key, func() (interface{}, error) {
        return h.orderService.CreateOrder(r.Context(), h.getRequest(r))
    })

    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }

    json.NewEncoder(w).Encode(result)
}
```

### 3. Correlation IDs

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
    return uuid.New().String()
}

// Usage
func (s *OrderService) CreateOrder(ctx context.Context, req CreateOrderRequest) (*Order, error) {
    correlationID := GetCorrelationID(ctx)

    s.logger.Info("Creating order",
        "correlation_id", correlationID,
        "customer_id", req.CustomerID,
    )

    order, err := s.repo.Create(ctx, &Order{...})

    // Publish event with correlation ID
    event := map[string]interface{}{
        "order_id":        order.ID,
        "correlation_id":  correlationID,
        "customer_id":     req.CustomerID,
    }
    s.eventBus.Publish("order.created", event)

    return order, err
}
```

### 4. Saga Persistence

```sql
-- Saga state table
CREATE TABLE saga_instances (
    id UUID PRIMARY KEY,
    saga_type VARCHAR(100) NOT NULL,
    correlation_id UUID UNIQUE NOT NULL,
    current_state VARCHAR(50) NOT NULL,
    completed_steps TEXT[] NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for finding incomplete sagas
CREATE INDEX idx_saga_incomplete ON saga_instances(current_state, updated_at)
WHERE current_state NOT IN ('COMPLETED', 'COMPENSATED');

-- For recovery: find stale sagas and resume
SELECT * FROM saga_instances
WHERE current_state NOT IN ('COMPLETED', 'COMPENSATED')
AND updated_at < NOW() - INTERVAL '5 minutes';
```

```go
package saga

import (
    "context"
    "encoding/json"
    "time"
)

type SagaInstance struct {
    ID            string        `json:"id"`
    SagaType      string        `json:"saga_type"`
    CorrelationID string        `json:"correlation_id"`
    CurrentState  string        `json:"current_state"`
    CompletedSteps []string     `json:"completed_steps"`
    Payload       json.RawMessage `json:"payload"`
    CreatedAt     time.Time     `json:"created_at"`
    UpdatedAt     time.Time     `json:"updated_at"`
}

type SagaRepository interface {
    Create(ctx context.Context, saga *SagaInstance) error
    GetByID(ctx context.Context, id string) (*SagaInstance, error)
    Update(ctx context.Context, saga *SagaInstance) error
    FindIncomplete(ctx context.Context, olderThan time.Duration) ([]*SagaInstance, error)
}

func (s *SagaInstance) Save(ctx context.Context, repo SagaRepository) error {
    s.UpdatedAt = time.Now()
    if s.CreatedAt.IsZero() {
        s.CreatedAt = time.Now()
        return repo.Create(ctx, s)
    }
    return repo.Update(ctx, s)
}

// Recovery function
func RecoverIncompleteSagas(ctx context.Context, repo SagaRepository, handlers map[string]SagaHandler) error {
    incomplete, err := repo.FindIncomplete(ctx, 5*time.Minute)
    if err != nil {
        return err
    }

    for _, saga := range incomplete {
        handler, ok := handlers[saga.SagaType]
        if !ok {
            continue
        }

        // Resume or compensate
        if saga.CurrentState == "COMPENSATING" {
            _ = handler.Compensate(ctx, saga)
        } else {
            _ = handler.Resume(ctx, saga)
        }
    }

    return nil
}

type SagaHandler interface {
    Resume(ctx context.Context, saga *SagaInstance) error
    Compensate(ctx context.Context, saga *SagaInstance) error
}
```

---

## Summary

Saga pattern enables distributed transactions without 2PC:
- **Each step is a local transaction**
- **Compensation on failure**
- **Eventual consistency**
- **Choose choreography or orchestration based on complexity**
