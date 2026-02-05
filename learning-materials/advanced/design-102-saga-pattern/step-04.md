# Step 04: Orchestration - Central Coordinator Sagas

---

## What is Orchestration?

**Orchestration** = Central coordinator that directs the saga.

Think of it like a conductor leading an orchestra: the conductor (orchestrator) tells each section (service) when to play and what to do.

```
┌─────────────────────────────────────────────────────────────┐
│                   Saga Orchestrator                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  State Machine:                                       │  │
│  │  STARTED → COMPENSATING → COMPLETED / FAILED         │  │
│  │                                                       │  │
│  │  Saga Log:                                           │  │
│  │  - Step 1: CreateOrder ✓                              │  │
│  │  - Step 2: ChargePayment ✓                            │  │
│  │  - Step 3: ReserveInventory ⏳                         │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
           │              │               │
           ▼              ▼               ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │  Order   │  │ Payment  │  │Inventory │
    │ Service  │  │ Service  │  │ Service  │
    └──────────┘  └──────────┘  └──────────┘
```

---

## Example: Order Flow with Orchestration

```go
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
    }

    // Execute each step sequentially
    // If any step fails, compensate in reverse

    // Step 1: Create Order
    order, err := o.createOrder(ctx, req, saga)
    if err != nil {
        return fmt.Errorf("create order: %w", err)
    }

    // Step 2: Charge Payment
    paymentID, err := o.chargePayment(ctx, order, saga)
    if err != nil {
        // Compensate: cancel order
        _ = o.cancelOrder(ctx, order.ID)
        return fmt.Errorf("charge payment: %w", err)
    }

    // Step 3: Reserve Inventory
    if err := o.reserveInventory(ctx, order.ID, saga); err != nil {
        // Compensate in reverse:
        // 1. Release inventory (nothing to release)
        // 2. Refund payment
        // 3. Cancel order
        _ = o.refundPayment(ctx, paymentID)
        _ = o.cancelOrder(ctx, order.ID)
        return fmt.Errorf("reserve inventory: %w", err)
    }

    // Step 4: Confirm Order
    if err := o.confirmOrder(ctx, order.ID, saga); err != nil {
        // Compensate in reverse
        _ = o.releaseInventory(ctx, order.ID)
        _ = o.refundPayment(ctx, paymentID)
        _ = o.cancelOrder(ctx, order.ID)
        return fmt.Errorf("confirm order: %w", err)
    }

    saga.Status = "completed"
    o.sagaLog.Save(ctx, saga)
    return nil
}
```

---

## The Saga Log

The orchestrator persists state after each step:

```sql
CREATE TABLE saga_log (
    id UUID PRIMARY KEY,
    saga_id UUID NOT NULL,
    step_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- 'executing', 'completed', 'failed', 'compensating'
    result JSONB,                  -- Store step result (e.g., payment_id)
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enables recovery after orchestrator crash
```

---

## Orchestration Pros and Cons

| Pros | Cons |
|------|------|
| ✅ Clear workflow logic | ❌ Orchestrator is SPOF (can be mitigated) |
| ✅ Easy to debug and monitor | ❌ More coupling between orchestrator and services |
| ✅ Centralized saga state | ❌ Single point of control |
| ✅ Easy to add/modify steps | ❌ Potential bottleneck |

---

## Mitigating the SPOF

```
┌─────────────────────────────────────────────────────────────┐
│  Mitigation Strategies for Orchestrator SPOF:              │
├─────────────────────────────────────────────────────────────┤
│  1. Persistent Saga Log                                   │
│     → Recover state after crash                            │
│                                                             │
│  2. Multiple Orchestrator Instances (HA)                   │
│     → Use leader election (etcd)                           │
│     → Only one active, others standby                      │
│                                                             │
│  3. Automatic Recovery                                     │
│     → On startup, find incomplete sagas                     │
│     → Resume or compensate                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Check

Before moving on, make sure you understand:

1. What is orchestration? (Central coordinator directing the flow)
2. What is the saga log? (Persistent state for recovery)
3. What's the main benefit? (Clear workflow, centralized state)
4. What's the main drawback? (Orchestrator is SPOF)
5. How do you mitigate SPOF? (Persistent log, HA, recovery)

---

**Ready to compare choreography vs orchestration? Read `step-05.md`**
