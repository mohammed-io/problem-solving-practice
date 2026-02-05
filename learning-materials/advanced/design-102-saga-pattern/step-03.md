# Step 03: Choreography - Event-Driven Sagas

---

## What is Choreography?

**Choreography** = Decentralized coordination through events.

Think of it like a dance: each dancer knows their own moves and responds to the music (events). No single conductor tells everyone what to do.

```
┌─────────────┐      Event       ┌─────────────┐
│   Order     │  OrderCreated    │  Payment    │
│  Service    │─────────────────▶│  Service    │
└─────────────┘                  └──────┬──────┘
                                        │
                                        │ PaymentCharged
                                        ▼
                                 ┌─────────────┐
                                 │  Inventory  │
                                 │  Service    │
                                 └─────────────┘

No central coordinator. Each service:
- Emits events when something happens
- Listens for events it cares about
- Acts independently
```

---

## Example: Order Flow with Choreography

```go
// Order Service publishes event
type OrderService struct {
    repo     OrderRepository
    eventBus *EventBus
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

    // Publish event - fire and forget
    s.eventBus.Publish("order.created", OrderCreatedEvent{
        OrderID:    order.ID,
        CustomerID: order.CustomerID,
        Total:      order.Total,
    })

    return order, nil
}

// Payment Service listens and acts
type PaymentService struct {
    repo     PaymentRepository
    eventBus *EventBus
}

func (s *PaymentService) Start(ctx context.Context) {
    // Subscribe to order.created events
    s.eventBus.Subscribe("order.created", func(data []byte) error {
        var event OrderCreatedEvent
        json.Unmarshal(data, &event)

        // Charge payment
        payment, err := s.ChargePayment(ctx, event.OrderID, event.Total)
        if err != nil {
            // Publish failure event
            s.eventBus.Publish("payment.failed", map[string]string{
                "order_id": event.OrderID,
                "error":    err.Error(),
            })
            return err
        }

        // Publish success event
        s.eventBus.Publish("payment.charged", PaymentChargedEvent{
            OrderID:   event.OrderID,
            PaymentID: payment.ID,
        })

        return nil
    })
}

// Inventory Service listens for payment.charged
type InventoryService struct {
    repo     InventoryRepository
    eventBus *EventBus
}

func (s *InventoryService) Start(ctx context.Context) {
    s.eventBus.Subscribe("payment.charged", func(data []byte) error {
        var event PaymentChargedEvent
        json.Unmarshal(data, &event)

        // Reserve inventory
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
```

---

## Event Flow

```
Step 1: Order Service
  └─▶ Publishes: OrderCreated
      └─▶ {order_id: "123", customer_id: "456", total: 99.99}

Step 2: Payment Service (subscribed to OrderCreated)
  └─▶ Receives: OrderCreated
  └─▶ Charges payment
  └─▶ Publishes: PaymentCharged
      └─▶ {order_id: "123", payment_id: "xyz"}

Step 3: Inventory Service (subscribed to PaymentCharged)
  └─▶ Receives: PaymentCharged
  └─▶ Reserves inventory
  └─▶ Publishes: InventoryReserved
      └─▶ {order_id: "123"}
```

---

## Choreography Pros and Cons

| Pros | Cons |
|------|------|
| ✅ No single point of failure | ❌ Workflow logic spread across services |
| ✅ Services loosely coupled | ❌ Hard to see the full flow |
| ✅ Easy to add new services | ❌ Difficult to debug |
| ✅ Scales horizontally | ❌ No central state to query |

---

## When to Use Choreography

```
✅ Good for:
   - Simple workflows (2-3 steps)
   - Independent teams
   - High availability requirements
   - Event-driven architectures

❌ Avoid for:
   - Complex workflows (5+ steps)
   - Business-critical transactions
   - When you need audit trails
   - When debugging complexity is a concern
```

---

## Quick Check

Before moving on, make sure you understand:

1. What is choreography? (Decentralized event-driven coordination)
2. How do services communicate? (Through events, not direct calls)
3. What's the main benefit? (No SPOF, loose coupling)
4. What's the main drawback? (Hard to see full flow, difficult debugging)

---

**Ready to learn about orchestration? Read `step-04.md`**
