# Step 1: Event Schema Design

---

## Good Event Schema

```json
{
  "eventId": "evt_01hXyZ123ABC",
  "aggregateId": "order_123",
  "aggregateType": "Order",
  "eventType": "OrderConfirmed",
  "data": {
    "restaurantId": 789,
    "confirmedBy": "user_456",
    "estimatedPrepTime": 30
  },
  "metadata": {
    "userId": "user_456",
    "timestamp": "2024-01-15T14:05:23.123Z",
    "correlationId": "req_xyz789",
    "causationId": "cmd_abc456"
  },
  "version": 2,
  "createdAt": "2024-01-15T14:05:23.123Z"
}
```

**Key fields:**
- `eventId`: Unique identifier for this event
- `aggregateId`: Entity this event belongs to
- `aggregateType`: Type of entity (Order, User, Restaurant)
- `eventType`: What happened
- `data`: Event-specific data
- `metadata`: Auditing info (who, when, why)
- `version`: Sequence number (prevents concurrency issues)

---

## Event Types for Order

```go
type OrderEvent interface{}

type OrderCreated struct {
    OrderID       OrderID
    UserID        UserID
    RestaurantID  RestaurantID
    Items         []Item
    DeliveryAddress Address
    EstimatedDelivery time.Time
}

type OrderConfirmed struct {
    OrderID       OrderID
    RestaurantID  RestaurantID
    ConfirmedAt   time.Time
}

type OrderPreparing struct {
    OrderID       OrderID
    EstimatedTime time.Duration
}

type OrderReady struct {
    OrderID       OrderID
    ReadyAt       time.Time
}

type OrderPickedUp struct {
    OrderID       OrderID
    DriverID      DriverID
    PickedUpAt    time.Time
}

type OrderDelivered struct {
    OrderID       OrderID
    DeliveredAt   time.Time
    Rating        *int  // Optional
}

type OrderCancelled struct {
    OrderID       OrderID
    Reason        string
    CancelledBy   UserID
    CancelledAt   time.Time
}
```

---

## Why This Matters

Good event schema:
- **Immutable:** Events never change
- **Append-only:** Always add, never modify
- **Ordered:** version ensures sequence
- **Auditable:** metadata tracks who/when
- **Serializable:** JSON (or any format) works

---

## Quick Check

Before moving on, make sure you understand:

1. What's an event aggregate? (Entity that events belong to, like Order or User)
2. What's the version field for? (Prevents concurrency issues, ensures ordering)
3. What's the difference between eventId and aggregateId? (eventId = unique event, aggregateId = entity)
4. What's in the metadata field? (Auditing info: who, when, why - correlationId, causationId)
5. Why should events be immutable? (They represent facts that happened, can't change history)

---

**Continue to `step-02.md`**
