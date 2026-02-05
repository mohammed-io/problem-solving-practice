# Step 06: Failure Scenarios and Recovery

---

## The Problem

Things fail. How do you recover?

```
Common failure scenarios:

1. Orchestrator crashes mid-saga
   → How do you know where to resume?

2. Service temporarily unavailable
   → Do you retry? Give up? Compensate?

3. Compensating transaction fails
   → Now you're in a really bad state

4. Duplicate events (network retry)
   → How do you avoid double-processing?
```

---

## Scenario 1: Orchestrator Crash

**Problem:** Orchestrator crashes after completing step 2 of 4.

```
┌─────────────────────────────────────────────────────────────┐
│  Saga State Before Crash:                                  │
│  ┌──────────────────────────────────────────────┐          │
│  │  Step 1: CreateOrder ✓ (result: order-123)    │          │
│  │  Step 2: ChargePayment ✓ (result: pay-456)    │          │
│  │  Step 3: ReserveInventory ⏳ (not started)     │          │
│  │  Step 4: ConfirmOrder ⏳ (not started)        │          │
│  └──────────────────────────────────────────────┘          │
│                                                             │
│  💥 Orchestrator crashes!                                  │
└─────────────────────────────────────────────────────────────┘
```

**Solution: Saga Log Recovery**

```go
// On startup, find incomplete sagas
func (o *OrderSagaOrchestrator) RecoverIncompleteSagas(ctx context.Context) error {
    incomplete, err := o.sagaLog.FindByStatus(ctx, []string{"started", "compensating"})
    if err != nil {
        return err
    }

    for _, saga := range incomplete {
        // Determine which steps completed
        completedSteps := saga.GetCompletedSteps()

        // Resume from last step
        if saga.Status == "compensating" {
            // Continue compensating
            o.continueCompensation(ctx, saga)
        } else {
            // Resume execution from next step
            o.resumeExecution(ctx, saga, completedSteps)
        }
    }

    return nil
}

func (o *OrderSagaOrchestrator) resumeExecution(ctx context.Context, saga *SagaLog, completedSteps []string) error {
    // Skip already completed steps
    nextStep := len(completedSteps) + 1

    switch nextStep {
    case 3: // ReserveInventory
        if err := o.reserveInventory(ctx, saga); err != nil {
            o.compensate(ctx, saga, completedSteps)
            return err
        }
        fallthrough
    case 4: // ConfirmOrder
        if err := o.confirmOrder(ctx, saga); err != nil {
            o.compensate(ctx, saga, completedSteps)
            return err
        }
    }

    saga.Status = "completed"
    return o.sagaLog.Save(ctx, saga)
}
```

---

## Scenario 2: Transient Service Failure

**Problem:** Payment service times out. Do you retry?

```
┌─────────────────────────────────────────────────────────────┐
│  Orchestrator tries to charge payment:                      │
│                                                             │
│  Attempt 1: timeout (no response)                          │
│  Attempt 2: timeout (no response)                          │
│  Attempt 3: timeout (no response)                          │
│                                                             │
│  Question: Keep trying? Or give up?                        │
└─────────────────────────────────────────────────────────────┘
```

**Solution: Retry with Limits**

```go
type RetryConfig struct {
    MaxAttempts int
    BackoffBase  time.Duration
    Timeout      time.Duration
}

func (o *OrderSagaOrchestrator) chargePaymentWithRetry(ctx context.Context, order *Order) (string, error) {
    config := RetryConfig{
        MaxAttempts: 3,
        BackoffBase: 100 * time.Millisecond,
        Timeout:      5 * time.Second,
    }

    for attempt := 1; attempt <= config.MaxAttempts; attempt++ {
        paymentID, err := o.paymentSvc.ChargePayment(ctx, order.ID, order.Total)

        if err == nil {
            return paymentID, nil // Success!
        }

        // Check if error is retryable
        if !isRetryable(err) {
            return "", fmt.Errorf("non-retryable error: %w", err)
        }

        // Exponential backoff
        backoff := config.BackoffBase * time.Duration(1<<(attempt-1))
        select {
        case <-time.After(backoff):
            continue
        case <-ctx.Done():
            return "", ctx.Err()
        }
    }

    return "", fmt.Errorf("failed after %d attempts", config.MaxAttempts)
}

func isRetryable(err error) bool {
    // Retry on timeout, connection refused
    // Don't retry on "insufficient funds", "card declined"
    return errors.Is(err, context.DeadlineExceeded) ||
           errors.Is(err, context.Canceled)
}
```

---

## Scenario 3: Compensation Failure

**Problem:** Refund fails! Now what?

```
┌─────────────────────────────────────────────────────────────┐
│  Original flow fails at inventory, need to compensate:      │
│                                                             │
│  Step 1: CreateOrder ✓ (needs: cancel)                     │
│  Step 2: ChargePayment ✓ (needs: refund)                    │
│  Step 3: ReserveInventory ✗ (failed, so compensate)          │
│                                                             │
│  Compensation:                                             │
│    Refund payment... ❌ Gateway down!                      │
│    Cancel order... ✓                                        │
│                                                             │
│  Now: Payment was charged but not refunded!                │
│  → Manual intervention required                             │
└─────────────────────────────────────────────────────────────┘
```

**Solution: Dead Letter Queue + Human Intervention**

```go
func (o *OrderSagaOrchestrator) compensate(ctx context.Context, saga *SagaLog) error {
    completedSteps := saga.GetCompletedSteps()

    // Compensate in reverse order
    for i := len(completedSteps) - 1; i >= 0; i-- {
        step := completedSteps[i]

        var err error
        switch step.Name {
        case "charge_payment":
            err = o.refundPayment(ctx, step.Result)
        case "create_order":
            err = o.cancelOrder(ctx, step.Result)
        }

        if err != nil {
            // Compensation failed!
            // 1. Log the failure
            o.logger.Error("compensation_failed",
                zap.String("saga_id", saga.SagaID),
                zap.String("step", step.Name),
                zap.Error(err),
            )

            // 2. Move to dead letter queue
            o.deadLetterQueue.Send(DeadLetterMessage{
                SagaID:   saga.SagaID,
                Step:     step.Name,
                Error:    err.Error(),
                Requires: "manual_intervention",
            })

            // 3. Mark as failed (not compensated)
            saga.Status = "compensation_failed"
            o.sagaLog.Save(ctx, saga)

            return ErrCompensationFailed
        }
    }

    saga.Status = "compensated"
    return o.sagaLog.Save(ctx, saga)
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. How do you recover from orchestrator crash? (Resume from saga log)
2. When do you retry? (Transient errors, with backoff)
3. What if compensation fails? (Dead letter queue, manual intervention)
4. What is the saga log used for? (Recovery, audit trail)

---

**Ready for production concerns? Read `step-07.md`**
