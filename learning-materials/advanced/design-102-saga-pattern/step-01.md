# Step 01: Understanding Sagas

---

## What is a Saga?

A **saga** is a sequence of local transactions where each transaction updates data within a single service. If one step fails, compensating transactions undo the changes made by preceding steps.

**Key insight:** You can't have ACID across services, but you CAN have eventual consistency through sagas.

---

## Question 1: Consistency Without Distributed Transactions

**Answer: Use Sagas with Compensation**

Instead of one big transaction that spans services:

```
❌ Distributed Transaction (2PC):
Service1 ──┐
             ├──▶ Coordinator (locks all)
Service2 ──┤   (slow, fragile, blocks)
             │
Service3 ──┘

✓ Saga:
Service1 ──▶ Service2 ──▶ Service3 (sequence)
On fail: Service3 ──▶ Service2 ──▶ Service1 (compensate)
```

Each service does its own local transaction. If something fails, run compensating transactions to undo.

---

## Question 2: Payment Success, Inventory Fails

**Execute compensating transactions in reverse order:**

```go
// Forward flow (what happened)
// 1. OrderService.CreateOrder() ✓
// 2. PaymentService.ChargePayment() ✓
// 3. InventoryService.ReserveInventory() ✗ FAIL

// Compensating flow (reverse order)
// 1. PaymentService.RefundPayment() ← compensates step 2
// 2. OrderService.CancelOrder() ← compensates step 1
```

**Result:** Customer is refunded, order is cancelled. System is consistent.

---

## Question 3: Handling Compensation

**Compensation must be:**

1. **Idempotent** - Can be called multiple times safely
2. **Reliable** - Must eventually succeed
3. **Reversible** - Must undo the original operation

```go
package saga

import (
    "context"
    "fmt"
)

type PaymentService struct {
    repo PaymentRepository
    gateway PaymentGateway
}

func (s *PaymentService) ChargePayment(ctx context.Context, orderID string, amount float64) (string, error) {
    payment := &Payment{
        ID:        generateID(),
        OrderID:   orderID,
        Amount:    amount,
        Status:    "charged",
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

    // Check if already refunded (idempotent)
    if payment.Status == "refunded" {
        return nil // Already compensated, still success
    }

    // Update status
    payment.Status = "refunded"
    if err := s.repo.Update(ctx, payment); err != nil {
        return err
    }

    // Actually process refund with payment gateway
    return s.gateway.Refund(payment.ChargeID)
}
```

---

**Still thinking about choreography vs orchestration? Read `step-02.md`**
