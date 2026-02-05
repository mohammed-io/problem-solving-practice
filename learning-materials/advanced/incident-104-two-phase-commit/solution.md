# Solution: Two-Phase Commit Failure

---

## Root Cause

**2PC is a blocking protocol.** When coordinator crashes during COMMIT phase, participants are stuck in PREPARED state with locked resources.

---

## Solutions

### Solution 1: Recovery Protocol

```go
// Participant recovery on restart
func RecoverPreparedTransactions() {
    prepared := GetTransactionsInState("PREPARED")

    for _, tx := range prepared {
        // Try to contact coordinator
        status := QueryCoordinator(tx.CoordinatorID, tx.TransactionID)

        switch status {
        case "COMMITTED":
            Commit(tx)
        case "ABORTED":
            Rollback(tx)
        case "UNKNOWN":
            // Coordinator gone - use heuristic
            if time.Since(tx.CreatedAt) > HEURISTIC_TIMEOUT {
                if tx.Critical {
                    // Payment: assume commit
                    HeuristicCommit(tx)
                    LogHeuristicDecision(tx, "COMMIT")
                } else {
                    // Inventory: assume abort
                    HeuristicAbort(tx)
                    LogHeuristicDecision(tx, "ABORT")
                }
            }
        }
    }
}
```

### Solution 2: Use Saga Instead

```go
type SagaStep struct {
    Execute   func() error
    Compensate func() error
}

func ExecuteOrderSaga(order Order) error {
    steps := []SagaStep{
        {
            Execute:   func() error { return paymentService.Charge(order.Total) },
            Compensate: func() error { return paymentService.Refund(order.Total) },
        },
        {
            Execute:   func() error { return inventoryService.Reserve(order.Items) },
            Compensate: func() error { return inventoryService.Release(order.Items) },
        },
        {
            Execute:   func() error { return shippingService.Schedule(order.Address) },
            Compensate: func() error { return shippingService.Cancel(order.ShipmentID) },
        },
    }

    completed := 0
    for i, step := range steps {
        if err := step.Execute(); err != nil {
            // Compensate completed steps
            for j := i - 1; j >= 0; j-- {
                steps[j].Compensate()
            }
            return err
        }
        completed++
    }
    return nil
}
```

### Solution 3: Idempotency + Message Queue

```go
// Instead of synchronous 2PC, use async messaging with idempotency
func ProcessOrder(order Order) error {
    // Record intent
    intent := CreateOrderIntent(order)

    // Send messages (will retry until ACK)
    messageBus.Publish("payment.charge", intent.ID, order.PaymentInfo)
    messageBus.Publish("inventory.reserve", intent.ID, order.Items)
    messageBus.Publish("shipping.schedule", intent.ID, order.ShippingInfo)

    return nil
}

// Each service processes idempotently
func HandleChargeMessage(msg Message) error {
    if alreadyProcessed(msg.ID) {
        return nil
    }
    chargePayment(msg.Data)
    markProcessed(msg.ID)
}
```

---

## Trade-offs

| Approach | Atomic | Available | Latency | Complexity |
|----------|--------|-----------|---------|------------|
| **2PC** | Yes | No (blocks) | High | Medium |
| **3PC** | Yes | Better | Very High | High |
| **Saga** | No (eventual) | Yes | Low | High |
| **Async + Idempotency** | No (eventual) | Yes | Lowest | Medium |

**Recommendation:** Use Saga for most business transactions. Reserve 2PC for cases requiring true atomicity (financial settlements between banks).

---

**Next Problem:** `advanced/incident-105-leader-election/`
