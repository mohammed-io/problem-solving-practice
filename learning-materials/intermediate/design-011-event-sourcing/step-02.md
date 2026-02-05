# Step 2: Storage and Read Models

---

## Storage: Event Store Table

```sql
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_id VARCHAR(100) NOT NULL,
    aggregate_type VARCHAR(50) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    data JSONB NOT NULL,
    metadata JSONB,
    version BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (aggregate_id, version)  -- Prevent lost updates
);

CREATE INDEX idx_events_aggregate ON events(aggregate_id, version);
CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_created ON events(created_at);

-- For temporal queries
CREATE INDEX idx_events_aggregate_time ON events(aggregate_id, created_at);
```

**The UNIQUE constraint handles concurrency:**
```
Process A: INSERT events (aggregate_id='order_123', version=5) → Success
Process B: INSERT events (aggregate_id='order_123', version=5) → ERROR!
→ Process B retries, reads version 6, inserts version 7 → Success
```

---

## Read Model: CQRS

**Command side:** Append events to event store

**Query side:** Build projections for fast reads

```
┌─────────────────────────────────────────────────────────┐
│                    Command Side                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Event Store                         │   │
│  │  append-only, ordered, versioned                │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────┘
                          │ Events
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    Query Side                            │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Orders     │  │  Dashboard   │  │  Analytics   │ │
│  │  Projection  │  │  Projection  │  │  Projection  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Order projection table:**
```sql
CREATE TABLE read_model_orders (
    order_id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    restaurant_id BIGINT,
    status VARCHAR(50) NOT NULL,
    items JSONB NOT NULL,
    total_amount DECIMAL(10,2),
    delivery_address TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    current_version BIGINT NOT NULL,  -- For sync checking

    -- Denormalized for queries
    user_name VARCHAR(100),
    restaurant_name VARCHAR(100),
    driver_name VARCHAR(100),
    estimated_delivery TIMESTAMPTZ
);

CREATE INDEX idx_orders_user ON read_model_orders(user_id);
CREATE INDEX idx_orders_status ON read_model_orders(status);
CREATE INDEX idx_orders_created ON read_model_orders(created_at DESC);
```

**Projection handler:**
```go
func (p *OrderProjection) Handle(event Event) error {
    switch e := event.Data.(type) {
    case *OrderCreated:
        db.Exec(`
            INSERT INTO read_model_orders
            (order_id, user_id, status, items, created_at, current_version)
            VALUES ($1, $2, 'created', $3, $4, $5)
        `, e.OrderID, e.UserID, e.Items, e.CreatedAt, event.Version)

    case *OrderConfirmed:
        db.Exec(`
            UPDATE read_model_orders
            SET restaurant_id = $1, status = 'confirmed', current_version = $2
            WHERE order_id = $3
        `, e.RestaurantID, event.Version, e.OrderID)

    case *OrderCancelled:
        db.Exec(`
            UPDATE read_model_orders
            SET status = 'cancelled', current_version = $1
            WHERE order_id = $2
        `, event.Version, e.OrderID)
    }
    return nil
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's CQRS? (Command Query Responsibility Segregation - separate read/write models)
2. What's the event store? (Append-only log of all events with versioning)
3. How does the UNIQUE constraint handle concurrency? (Prevents duplicate versions, causes retry)
4. What's a projection? (Read model built from events for fast queries)
5. Why separate command and query sides? (Optimize each: writes for consistency, reads for performance)

---

**Continue to `solution.md`**
