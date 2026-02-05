# Step 02: Three-Phase Commit and Alternatives

---

## 3PC (Three-Phase Commit)

Adds "canCommit?" phase to prevent blocking:

```
Phase 1: CanCommit?
  Coordinator → Participants: CanCommit?
  Participants → Coordinator: Yes/No

Phase 2: PreCommit
  If all Yes: Coordinator → Participants: PreCommit
  Participants enter PRECOMMITTED state (non-blocking)

Phase 3: DoCommit
  Coordinator → Participants: DoCommit
```

**Improvement:** Participants can timeout and decide (with coordination).

**Problem:** Still complex, requires reliable messaging.

---

## Better Alternative: Saga Pattern

Break transaction into compensatable steps:

```go
package saga

import (
    "context"
    "fmt"
    "log"
)

type SagaState int

const (
    StatePending SagaState = iota
    StateStarted
    StateCompleted
    StateCompensating
    StateCompensated
    StateFailed
)

type SagaStep struct {
    Execute    func(ctx context.Context) error
    Compensate func(ctx context.Context) error
}

type OrderFulfillmentSaga struct {
    orderID        string
    steps          []SagaStep
    completedSteps []int
    state          SagaState
}

func NewOrderFulfillmentSaga(orderID string) *OrderFulfillmentSaga {
    return &OrderFulfillmentSaga{
        orderID: orderID,
        state:   StatePending,
        steps: []SagaStep{
            {
                Execute:    func(ctx context.Context) error { return reserveInventory(ctx, orderID) },
                Compensate: func(ctx context.Context) error { return releaseInventory(ctx, orderID) },
            },
            {
                Execute:    func(ctx context.Context) error { return chargePayment(ctx, orderID) },
                Compensate: func(ctx context.Context) error { return refundPayment(ctx, orderID) },
            },
            {
                Execute:    func(ctx context.Context) error { return scheduleShipping(ctx, orderID) },
                Compensate: func(ctx context.Context) error { return cancelShipping(ctx, orderID) },
            },
        },
    }
}

func (s *OrderFulfillmentSaga) Execute(ctx context.Context) error {
    s.state = StateStarted

    for i, step := range s.steps {
        if err := step.Execute(ctx); err != nil {
            log.Printf("Step %d failed: %v", i, err)
            s.state = StateCompensating
            return s.compensate(ctx)
        }
        s.completedSteps = append(s.completedSteps, i)
    }

    s.state = StateCompleted
    return nil
}

func (s *OrderFulfillmentSaga) compensate(ctx context.Context) error {
    // Compensate in reverse order
    for i := len(s.completedSteps) - 1; i >= 0; i-- {
        stepIdx := s.completedSteps[i]
        if err := s.steps[stepIdx].Compensate(ctx); err != nil {
            log.Printf("Compensation %d failed: %v", stepIdx, err)
        }
    }
    s.state = StateCompensated
    return fmt.Errorf("saga failed after compensation")
}

// Mock service functions
func reserveInventory(ctx context.Context, orderID string) error {
    log.Printf("Reserving inventory for order %s", orderID)
    return nil
}

func releaseInventory(ctx context.Context, orderID string) error {
    log.Printf("Releasing inventory for order %s", orderID)
    return nil
}

func chargePayment(ctx context.Context, orderID string) error {
    log.Printf("Charging payment for order %s", orderID)
    return nil
}

func refundPayment(ctx context.Context, orderID string) error {
    log.Printf("Refunding payment for order %s", orderID)
    return nil
}

func scheduleShipping(ctx context.Context, orderID string) error {
    log.Printf("Scheduling shipping for order %s", orderID)
    return nil
}

func cancelShipping(ctx context.Context, orderID string) error {
    log.Printf("Canceling shipping for order %s", orderID)
    return nil
}
```

**Trade-off:** Eventually consistent (not atomic), but available.

---

## Visual: Saga vs 2PC

```
┌─────────────────────────────────────────────────────────────────┐
│  2PC vs Saga Tradeoffs:                                        │
│                                                                │
│  2PC (Two-Phase Commit):                                       │
│    → Atomic: all or nothing                                   │
│    → Blocking: participants wait for coordinator              │
│    → Real-time: immediate consistency                          │
│    → Use: Payments, inventory (critical systems)               │
│                                                                │
│  Saga (Compensating Transactions):                            │
│    → Eventually consistent                                    │
│    → Non-blocking: each step commits independently            │
│    → Async: compensation happens in background                │
│    → Use: Order fulfillment, multi-service workflows          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Summary: Choosing Between 2PC and Saga

| Factor | 2PC | Saga |
|--------|-----|------|
| Consistency | Strong (atomic) | Eventual |
| Availability | Low (blocking) | High (non-blocking) |
| Complexity | Medium | Medium |
| Lock Duration | Short (transaction) | Long (until compensate) |
| Use Case | Critical operations | Business workflows |

---

## Quick Check

Before moving on, make sure you understand:

1. What does 3PC add over 2PC? (CanCommit phase to prevent blocking)
2. What is the saga pattern? (Long transactions with compensation)
3. How does saga handle failures? (Compensating transactions in reverse)
4. When should you use 2PC vs saga? (2PC for critical atomic, saga for workflows)
5. What's the main tradeoff of saga? (Eventual consistency, not atomic)

---

**Continue to `solution.md`**
