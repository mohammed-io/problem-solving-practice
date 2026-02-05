# Step 02: Choreography vs Orchestration

---

## Question 4: Choreography vs Orchestration

### Choreography (Event-Driven)

**No central coordinator.** Services emit events and react to events from other services.

```go
package choreography

import (
    "context"
    "encoding/json"
)

// Order Service publishes event
type OrderService struct {
    repo     OrderRepository
    eventBus *EventBus
}

type OrderCreatedEvent struct {
    OrderID    string  `json:"order_id"`
    CustomerID string  `json:"customer_id"`
    Total      float64 `json:"total"`
}

func (s *OrderService) CreateOrder(ctx context.Context, req CreateOrderRequest) (*Order, error) {
    order := &Order{
        ID:         generateID(),
        CustomerID: req.CustomerID,
        Total:      req.Total,
        Status:     "pending",
    }

    if err := s.repo.Create(ctx, order); err != nil {
        return nil, err
    }

    // Publish event - don't wait for responses
    event := OrderCreatedEvent{
        OrderID:    order.ID,
        CustomerID: order.CustomerID,
        Total:      order.Total,
    }
    s.eventBus.Publish("order.created", event)

    return order, nil
}

// Payment Service listens and acts
type PaymentService struct {
    repo     PaymentRepository
    eventBus *EventBus
}

func (s *PaymentService) Start(ctx context.Context) {
    s.eventBus.Subscribe("order.created", func(data []byte) error {
        var event OrderCreatedEvent
        if err := json.Unmarshal(data, &event); err != nil {
            return err
        }

        payment, err := s.ChargePayment(ctx, event.OrderID, event.Total)
        if err != nil {
            s.eventBus.Publish("payment.failed", map[string]string{
                "order_id": event.OrderID,
                "error":    err.Error(),
            })
            return err
        }

        s.eventBus.Publish("payment.charged", PaymentChargedEvent{
            OrderID:   event.OrderID,
            PaymentID: payment.ID,
        })

        return nil
    })
}

func (s *PaymentService) ChargePayment(ctx context.Context, orderID string, amount float64) (*Payment, error) {
    payment := &Payment{
        ID:      generateID(),
        OrderID: orderID,
        Amount:  amount,
        Status:  "charged",
    }

    if err := s.repo.Create(ctx, payment); err != nil {
        return nil, err
    }

    return payment, nil
}

// Inventory Service listens
type InventoryService struct {
    repo     InventoryRepository
    eventBus *EventBus
}

type PaymentChargedEvent struct {
    OrderID   string `json:"order_id"`
    PaymentID string `json:"payment_id"`
}

func (s *InventoryService) Start(ctx context.Context) {
    s.eventBus.Subscribe("payment.charged", func(data []byte) error {
        var event PaymentChargedEvent
        if err := json.Unmarshal(data, &event); err != nil {
            return err
        }

        if err := s.ReserveInventory(ctx, event.OrderID); err != nil {
            s.eventBus.Publish("inventory.reservation.failed", map[string]string{
                "order_id": event.OrderID,
            })
            return err
        }

        s.eventBus.Publish("inventory.reserved", map[string]string{
            "order_id": event.OrderID,
        })

        return nil
    })
}

func (s *InventoryService) ReserveInventory(ctx context.Context, orderID string) error {
    // Reserve inventory logic
    return s.repo.Reserve(ctx, orderID)
}
```

**Pros:**
- No single point of failure
- Services are loosely coupled
- Easy to add new services

**Cons:**
- Workflow logic is spread across services
- Hard to see the full flow
- Debugging is difficult

---

### Orchestration (Central Coordinator)

**Central orchestrator directs the flow.**

```go
package orchestration

import (
    "context"
    "fmt"
    "time"
)

type SagaStep struct {
    Name       string
    Execute    func(ctx context.Context) (interface{}, error)
    Compensate func(ctx context.Context, result interface{}) error
    Result     interface{}
}

type SagaLogEntry struct {
    StepName    string      `json:"step_name"`
    Status      string      `json:"status"`
    Result      interface{} `json:"result,omitempty"`
    Error       string      `json:"error,omitempty"`
    CompletedAt time.Time   `json:"completed_at"`
}

type SagaLog struct {
    SagaID    string         `json:"saga_id"`
    Status    string         `json:"status"`
    Steps     []SagaLogEntry `json:"steps"`
    CreatedAt time.Time      `json:"created_at"`
    UpdatedAt time.Time      `json:"updated_at"`
}

type OrderSagaOrchestrator struct {
    orderRepo    OrderRepository
    paymentSvc   PaymentServiceClient
    inventorySvc InventoryServiceClient
    sagaLog      SagaLogRepository
}

func (o *OrderSagaOrchestrator) Execute(ctx context.Context, req CreateOrderRequest) error {
    sagaID := generateID()

    // Initialize saga log
    saga := &SagaLog{
        SagaID:    sagaID,
        Status:    "started",
        Steps:     make([]SagaLogEntry, 0),
        CreatedAt: time.Now(),
        UpdatedAt: time.Now(),
    }

    steps := []SagaStep{
        {
            Name: "create_order",
            Execute: func(ctx context.Context) (interface{}, error) {
                order := &Order{
                    ID:         sagaID,
                    CustomerID: req.CustomerID,
                    Total:      req.Total,
                    Status:     "pending",
                }
                if err := o.orderRepo.Create(ctx, order); err != nil {
                    return nil, fmt.Errorf("create order: %w", err)
                }
                return order.ID, nil
            },
            Compensate: func(ctx context.Context, result interface{}) error {
                orderID := result.(string)
                return o.orderRepo.Cancel(ctx, orderID)
            },
        },
        {
            Name: "charge_payment",
            Execute: func(ctx context.Context) (interface{}, error) {
                payment, err := o.paymentSvc.ChargePayment(ctx, sagaID, req.Total)
                if err != nil {
                    return nil, fmt.Errorf("charge payment: %w", err)
                }
                return payment.ID, nil
            },
            Compensate: func(ctx context.Context, result interface{}) error {
                paymentID := result.(string)
                return o.paymentSvc.RefundPayment(ctx, paymentID)
            },
        },
        {
            Name: "reserve_inventory",
            Execute: func(ctx context.Context) (interface{}, error) {
                if err := o.inventorySvc.ReserveInventory(ctx, sagaID); err != nil {
                    return nil, fmt.Errorf("reserve inventory: %w", err)
                }
                return nil, nil
            },
            Compensate: func(ctx context.Context, result interface{}) error {
                return o.inventorySvc.ReleaseReservation(ctx, sagaID)
            },
        },
        {
            Name: "confirm_order",
            Execute: func(ctx context.Context) (interface{}, error) {
                if err := o.orderRepo.Confirm(ctx, sagaID); err != nil {
                    return nil, fmt.Errorf("confirm order: %w", err)
                }
                return nil, nil
            },
            Compensate: nil, // No compensation needed for final step
        },
    }

    // Execute saga
    for i := range steps {
        step := &steps[i]

        o.logSagaStep(saga, step.Name, "executing", nil, "")

        result, err := step.Execute(ctx)
        if err != nil {
            o.logSagaStep(saga, step.Name, "failed", nil, err.Error())
            saga.Status = "compensating"
            o.sagaLog.Save(ctx, saga)

            // Compensate completed steps in reverse order
            if compErr := o.compensate(ctx, saga, steps[:i]); compErr != nil {
                saga.Status = "compensation_failed"
            } else {
                saga.Status = "failed"
            }
            o.sagaLog.Save(ctx, saga)

            return fmt.Errorf("saga failed: %w", err)
        }

        step.Result = result
        o.logSagaStep(saga, step.Name, "completed", result, "")
    }

    saga.Status = "completed"
    o.sagaLog.Save(ctx, saga)
    return nil
}

func (o *OrderSagaOrchestrator) compensate(ctx context.Context, saga *SagaLog, steps []SagaStep) error {
    // Compensate in reverse order
    for i := len(steps) - 1; i >= 0; i-- {
        step := steps[i]
        if step.Compensate == nil {
            continue
        }

        o.logSagaStep(saga, step.Name, "compensating", step.Result, "")

        if err := step.Compensate(ctx, step.Result); err != nil {
            o.logSagaStep(saga, step.Name, "compensation_failed", step.Result, err.Error())
            // Continue compensating despite errors
            continue
        }

        o.logSagaStep(saga, step.Name, "compensated", step.Result, "")
    }
    return nil
}

func (o *OrderSagaOrchestrator) logSagaStep(saga *SagaLog, stepName, status string, result interface{}, errMsg string) {
    entry := SagaLogEntry{
        StepName:    stepName,
        Status:      status,
        Result:      result,
        Error:       errMsg,
        CompletedAt: time.Now(),
    }
    saga.Steps = append(saga.Steps, entry)
    saga.UpdatedAt = time.Now()
}
```

**Pros:**
- Clear workflow logic
- Easy to debug and monitor
- Saga state is centralized

**Cons:**
- Orchestrator is a single point of failure (can be mitigated)
- More coupling between orchestrator and services

---

## Which to Choose?

| Use Choreography when... | Use Orchestration when... |
|---------------------------|---------------------------|
| Workflow is simple (2-3 steps) | Workflow is complex (5+ steps) |
| Services are independent | Services share business logic |
| You want high availability | You need centralized control |
| You're okay with eventual consistency | You need strong monitoring |

**Most teams:** Start with orchestration for complex workflows, choreography for simple ones.

---

## Recovery Patterns

### Orchestrator Crash Recovery

```go
// Recovery: On startup, find incomplete sagas
func (o *OrderSagaOrchestrator) RecoverIncompleteSagas(ctx context.Context) error {
    incomplete, err := o.sagaLog.FindByStatus(ctx, []string{"started", "compensating"})
    if err != nil {
        return err
    }

    for _, saga := range incomplete {
        // Resume from last completed step
        o.recoverSaga(ctx, saga)
    }

    return nil
}

func (o *OrderSagaOrchestrator) recoverSaga(ctx context.Context, saga *SagaLog) error {
    // Determine which steps completed and resume
    // This is a simplified version
    if saga.Status == "compensating" {
        // Continue compensating
        return o.continueCompensation(ctx, saga)
    }

    // Resume execution from last step
    return nil
}
```

### Duplicate Event Handling

```go
type PaymentEventHandler struct {
    processedLog ProcessedLogRepository
    svc          *PaymentService
}

func (h *PaymentEventHandler) HandleOrderCreated(ctx context.Context, event OrderCreatedEvent) error {
    // Use idempotency key
    idempotencyKey := event.CorrelationID

    // Check if already processed
    exists, err := h.processedLog.Exists(ctx, idempotencyKey)
    if err != nil {
        return err
    }
    if exists {
        return nil // Skip duplicate
    }

    // Process event
    if err := h.svc.ChargePayment(ctx, event.OrderID, event.Total); err != nil {
        return err
    }

    // Mark as processed
    return h.processedLog.Mark(ctx, idempotencyKey)
}
```

---

## Summary

| Pattern | Best For | Complexity |
|---------|----------|------------|
| **Choreography** | Simple flows, high scale | Distributed debugging |
| **Orchestration** | Complex flows, audit trails | Orchestrator SPOF |

**Recommendation:** Use orchestration for order flows (complex, business-critical). Use choreography for simple notifications.

---

**Now read `solution.md` for complete implementation examples.**
