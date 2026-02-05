# Solution: Event Sourcing for Order System

---

## Complete Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                              Client                                 │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           API Gateway                               │
└────────────────────────┬────────────────────────────────────────────┘
                         │
         ┌───────────────┴───────────────┐
         │                               │
         ▼                               ▼
┌─────────────────────┐         ┌─────────────────────┐
│   Command Service   │         │    Query Service    │
│   (Write path)      │         │    (Read path)      │
│                     │         │                     │
│  - Validate         │         │  - Fast reads       │
│  - Load events      │         │  - Denormalized     │
│  - Apply business   │         │  - Indexed          │
│    logic            │         │  - No replay        │
│  - Save events      │         │                     │
└──────────┬──────────┘         └─────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Event Store                                 │
│                    (PostgreSQL / Kafka)                             │
│                     Append-only log                                 │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         │ Events stream
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Projectors                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │   Orders     │  │   Dashboard  │  │  Analytics   │             │
│  │  Projection  │  │  Projection  │  │  Projection  │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Implementation

### 1. Event Store

```go
package eventstore

import (
    "context"
    "database/sql"
    "encoding/json"
    "errors"
    "github.com/google/uuid"
)

type Event struct {
    EventID       string                 `json:"eventId"`
    AggregateID   string                 `json:"aggregateId"`
    AggregateType string                 `json:"aggregateType"`
    EventType     string                 `json:"eventType"`
    Data          map[string]interface{} `json:"data"`
    Metadata      map[string]interface{} `json:"metadata"`
    Version       int64                  `json:"version"`
    CreatedAt     time.Time              `json:"createdAt"`
}

type EventStore struct {
    db *sql.DB
}

func (es *EventStore) AppendEvents(
    ctx context.Context,
    aggregateID string,
    aggregateType string,
    events []Event,
    expectedVersion *int64,  // For optimistic locking
) error {
    tx, _ := es.db.BeginTx(ctx, nil)
    defer tx.Rollback()

    // Check version if provided
    if expectedVersion != nil {
        var currentVersion int64
        err := tx.QueryRow(
            "SELECT COALESCE(MAX(version), 0) FROM events WHERE aggregate_id = $1",
            aggregateID,
        ).Scan(&currentVersion)

        if err != nil {
            return err
        }
        if currentVersion != *expectedVersion {
            return &ConcurrencyError{
                AggregateID:     aggregateID,
                ExpectedVersion: *expectedVersion,
                ActualVersion:   currentVersion,
            }
        }
    }

    // Insert events
    for i, event := range events {
        event.Version = *expectedVersion + int64(i) + 1
        event.EventID = uuid.New().String()
        event.CreatedAt = time.Now()

        dataJSON, _ := json.Marshal(event.Data)
        metadataJSON, _ := json.Marshal(event.Metadata)

        _, err := tx.ExecContext(ctx, `
            INSERT INTO events
            (id, aggregate_id, aggregate_type, event_type, data, metadata, version, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        `, event.EventID, aggregateID, aggregateType, event.EventType,
            dataJSON, metadataJSON, event.Version, event.CreatedAt)

        if err != nil {
            // Check for unique constraint violation (concurrency)
            if isUniqueViolation(err) {
                return &ConcurrencyError{
                    AggregateID:     aggregateID,
                    ExpectedVersion: event.Version - 1,
                    ActualVersion:   event.Version, // Someone else has this version
                }
            }
            return err
        }
    }

    return tx.Commit()
}

func (es *EventStore) LoadEvents(
    ctx context.Context,
    aggregateID string,
) ([]Event, error) {
    rows, err := es.db.QueryContext(ctx, `
        SELECT id, aggregate_id, aggregate_type, event_type,
               data, metadata, version, created_at
        FROM events
        WHERE aggregate_id = $1
        ORDER BY version ASC
    `, aggregateID)
    if err != nil {
        return nil, err
    }
    defer rows.Close()

    var events []Event
    for rows.Next() {
        var e Event
        var dataJSON, metadataJSON []byte
        rows.Scan(&e.EventID, &e.AggregateID, &e.AggregateType, &e.EventType,
            &dataJSON, &metadataJSON, &e.Version, &e.CreatedAt)
        json.Unmarshal(dataJSON, &e.Data)
        json.Unmarshal(metadataJSON, &e.Metadata)
        events = append(events, e)
    }

    return events, nil
}
```

### 2. Aggregate (Order)

```go
package domain

type OrderStatus string

const (
    StatusCreated    OrderStatus = "created"
    StatusConfirmed  OrderStatus = "confirmed"
    StatusPreparing  OrderStatus = "preparing"
    StatusReady      OrderStatus = "ready"
    StatusPickedUp   OrderStatus = "picked_up"
    StatusDelivered  OrderStatus = "delivered"
    StatusCancelled  OrderStatus = "cancelled"
)

type Order struct {
    ID              OrderID
    UserID          UserID
    RestaurantID    *RestaurantID
    DriverID        *DriverID
    Status          OrderStatus
    Items           []Item
    DeliveryAddress Address
    EstimatedTime   *time.Time
    CreatedAt       time.Time
    UpdatedAt       time.Time
    Version         int64
    // New events (not yet saved)
    pendingEvents   []Event
}

func (o *Order) Confirm(restaurantID RestaurantID, confirmedBy UserID) error {
    if o.Status != StatusCreated {
        return fmt.Errorf("cannot confirm order in status %s", o.Status)
    }

    o.RestaurantID = &restaurantID
    o.Status = StatusConfirmed
    o.UpdatedAt = time.Now()

    o.pendingEvents = append(o.pendingEvents, Event{
        EventType: "OrderConfirmed",
        Data: map[string]interface{}{
            "restaurantId": restaurantID,
            "confirmedBy":  confirmedBy,
        },
    })

    return nil
}

func (o *Order) Cancel(reason string, cancelledBy UserID) error {
    if o.Status == StatusDelivered {
        return errors.New("cannot cancel delivered order")
    }
    if o.Status == StatusPickedUp {
        return errors.New("cannot cancel order that's been picked up")
    }

    oldStatus := o.Status
    o.Status = StatusCancelled
    o.UpdatedAt = time.Now()

    o.pendingEvents = append(o.pendingEvents, Event{
        EventType: "OrderCancelled",
        Data: map[string]interface{}{
            "reason":      reason,
            "cancelledBy": cancelledBy,
            "oldStatus":   oldStatus,
        },
    })

    return nil
}

func (o *Order) GetUncommittedEvents() []Event {
    return o.pendingEvents
}

func (o *Order) MarkEventsAsCommitted() {
    o.pendingEvents = nil
}
```

### 3. Command Handler

```go
package command

type CommandHandler struct {
    eventStore *eventstore.EventStore
}

func (ch *CommandHandler) HandleConfirmOrder(
    ctx context.Context,
    cmd ConfirmOrderCommand,
) error {
    // Load existing events
    events, err := ch.eventStore.LoadEvents(ctx, cmd.OrderID)
    if err != nil {
        return err
    }

    // Rebuild aggregate
    order := domain.Order{}
    for _, event := range events {
        order.ApplyEvent(event)
    }

    // Check version for optimistic locking
    expectedVersion := order.Version

    // Execute command
    if err := order.Confirm(cmd.RestaurantID, cmd.ConfirmedBy); err != nil {
        return err
    }

    // Save new events
    newEvents := order.GetUncommittedEvents()
    if err := ch.eventStore.AppendEvents(
        ctx,
        cmd.OrderID,
        "Order",
        newEvents,
        &expectedVersion,
    ); err != nil {
        // Handle concurrency
        if concurrencyErr, ok := err.(*eventstore.ConcurrencyError); ok {
            // Retry logic
            return ch.HandleConfirmOrder(ctx, cmd)
        }
        return err
    }

    order.MarkEventsAsCommitted()
    return nil
}
```

### 4. Projection

```go
package projection

type OrderProjection struct {
    db *sql.DB
}

func (op *OrderProjection) Handle(event eventstore.Event) error {
    switch event.EventType {
    case "OrderCreated":
        return op.handleOrderCreated(event)

    case "OrderConfirmed":
        return op.handleOrderConfirmed(event)

    case "OrderCancelled":
        return op.handleOrderCancelled(event)

    default:
        return nil  // Ignore unknown events
    }
}

func (op *OrderProjection) handleOrderCreated(event eventstore.Event) error {
    data := event.Data
    _, err := op.db.Exec(`
        INSERT INTO read_model_orders
        (order_id, user_id, status, items, delivery_address,
         created_at, updated_at, current_version)
        VALUES ($1, $2, 'created', $3, $4, $5, $6, $7)
        ON CONFLICT (order_id) DO NOTHING
    `, event.AggregateID, data["userId"], data["items"],
        data["deliveryAddress"], event.CreatedAt, event.CreatedAt, event.Version)
    return err
}

func (op *OrderProjection) handleOrderConfirmed(event eventstore.Event) error {
    data := event.Data
    _, err := op.db.Exec(`
        UPDATE read_model_orders
        SET restaurant_id = $1,
            status = 'confirmed',
            updated_at = NOW(),
            current_version = $2
        WHERE order_id = $3 AND current_version < $2
    `, data["restaurantId"], event.Version, event.AggregateID)
    return err
}
```

### 5. Snapshotting

```sql
CREATE TABLE snapshots (
    aggregate_id VARCHAR(100) PRIMARY KEY,
    aggregate_type VARCHAR(50) NOT NULL,
    state JSONB NOT NULL,
    version BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

```go
func (es *EventStore) LoadEventsWithSnapshot(
    ctx context.Context,
    aggregateID string,
) ([]Event, error) {
    // Try to load snapshot first
    var snapshot struct {
        State   []byte
        Version int64
    }

    err := es.db.QueryRowContext(ctx, `
        SELECT state, version FROM snapshots WHERE aggregate_id = $1
    `, aggregateID).Scan(&snapshot.State, &snapshot.Version)

    if err == nil {
        // Snapshot found, load events after snapshot version
        rows, _ := es.db.QueryContext(ctx, `
            SELECT ... FROM events
            WHERE aggregate_id = $1 AND version > $2
            ORDER BY version ASC
        `, aggregateID, snapshot.Version)

        // Combine snapshot state + events
        return combineSnapshotAndEvents(snapshot, rows)
    }

    // No snapshot, load all events
    return es.LoadEvents(ctx, aggregateID)
}

func (es *EventStore) SaveSnapshot(
    ctx context.Context,
    aggregateID string,
    state interface{},
    version int64,
) error {
    stateJSON, _ := json.Marshal(state)
    _, err := es.db.ExecContext(ctx, `
        INSERT INTO snapshots (aggregate_id, aggregate_type, state, version)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (aggregate_id) DO UPDATE
        SET state = EXCLUDED.state, version = EXCLUDED.version
    `, aggregateID, "Order", stateJSON, version)
    return err
}

// Take snapshot every N events
func (ch *CommandHandler) maybeSaveSnapshot(
    ctx context.Context,
    order *domain.Order,
) {
    if order.Version%100 == 0 {  // Every 100 events
        ch.eventStore.SaveSnapshot(ctx, order.ID, order, order.Version)
    }
}
```

---

## Operational Concerns

### Monitoring

```promql
# Event processing lag
- alert: ProjectionLag
  expr: |
    events_total - events_processed_total > 1000
  labels:
    severity: warning

# Concurrency conflicts
- alert: HighConcurrencyConflicts
  expr: |
    rate(concurrency_conflicts_total[5m]) > 10
  labels:
    severity: warning

# Replay status
- alert: ReplayStuck
  expr: |
    time() - max(replay_last_timestamp) > 300
  labels:
    severity: critical
```

### Replaying Events

```bash
# Replay all events to rebuild projection
./replay-projection --projection=orders --from-beginning

# Replay from specific timestamp
./replay-projection --projection=orders --from="2024-01-01T00:00:00Z"

# Verify projection integrity
./verify-projection --projection=orders
```

### Migration Strategy

**When event schema changes:**

```go
// Version 1 event
{"type": "OrderCreated", "orderId": 123, "items": [...]}

// Version 2 event (added "customerNotes")
{"type": "OrderCreated", "orderId": 123, "items": [...], "customerNotes": ""}

// Upcaster transforms old to new
func upcastV1ToV2(event Event) Event {
    if event.Version == 1 && event.EventType == "OrderCreated" {
        event.Data["customerNotes"] = ""
        event.Version = 2
    }
    return event
}
```

---

## Trade-offs

| Aspect | Traditional CRUD | Event Sourcing |
|--------|------------------|----------------|
| **Complexity** | Simple | Complex |
| **Audit trail** | No (unless added) | Yes (built-in) |
| **Temporal queries** | Difficult | Easy |
| **Debugging** | Hard (can't replay) | Easy (replay events) |
| **Storage** | Current state only | All events (more storage) |
| **Read performance** | Direct read | Projection needed |
| **Schema changes** | Migration required | Upcasters |
| **Learning curve** | Low | High |

**When to use:**
- Need audit/compliance (finance, healthcare)
- Complex state transitions (orders, workflows)
- Need temporal queries (what was state at time T?)
- Debugging complex scenarios (replay to reproduce)

**When NOT to use:**
- Simple CRUD (just use traditional)
- Team lacks event sourcing experience
- Can't afford extra complexity

---

## Real Incident Reference

**Uber (2016):** Migrated from state-based to event-based system for ride state transitions. Enabled debugging complex ride scenarios and improved audit trail.

**LinkedIn (2013):** Event sourcing for user activity feed. Enabled "what you saw when" temporal queries and replay for bug reproduction.

---

**Next Problem:** `intermediate/postgres-010-cte-vs-subquery/`
