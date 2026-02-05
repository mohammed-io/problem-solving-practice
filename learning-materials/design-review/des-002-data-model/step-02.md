# Step 2: Improved Data Model

---

## Fixed Schema

```sql
-- Users table (source of truth)
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    tier user_tier NOT NULL DEFAULT 'free',  -- ENUM
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ  -- Soft delete
);

-- User tier ENUM
CREATE TYPE user_tier AS ENUM ('free', 'pro', 'enterprise');

-- Orders table
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status order_status NOT NULL DEFAULT 'pending',
    total_amount NUMERIC(10, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Order status ENUM with state machine
CREATE TYPE order_status AS ENUM (
    'pending', 'confirmed', 'processing',
    'shipped', 'delivered', 'cancelled', 'refunded'
);

-- Order items (separate table, not JSONB!)
CREATE TABLE order_items (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES products(id),
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(10, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Products table
CREATE TABLE products (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    sku VARCHAR(50) UNIQUE NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    inventory_count INT NOT NULL DEFAULT 0,
    metadata JSONB,  -- Flexible data for rarely-used fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Composite index for common query
CREATE INDEX orders_user_status ON orders(user_id, status);
CREATE INDEX orders_status_created ON orders(status, created_at DESC);

-- Cover index for hot query (includes columns to avoid table lookup)
CREATE INDEX orders_user_status_cover ON orders(user_id, status)
    INCLUDE (id, total_amount, created_at);
```

---

## Status Transition Logic

```sql
-- Function to enforce valid status transitions
CREATE FUNCTION update_order_status(
    p_order_id BIGINT,
    p_new_status order_status
) RETURNS boolean AS $$
DECLARE
    current_status order_status;
BEGIN
    SELECT status INTO current_status
    FROM orders
    WHERE id = p_order_id
    FOR UPDATE;

    -- Valid transitions
    IF p_new_status = 'cancelled' AND current_status NOT IN ('pending', 'confirmed') THEN
        RAISE EXCEPTION 'Cannot cancel order in status %', current_status;
    END IF;

    IF p_new_status = 'refunded' AND current_status != 'delivered' THEN
        RAISE EXCEPTION 'Can only refund delivered orders';
    END IF;

    UPDATE orders SET status = p_new_status WHERE id = p_order_id;
    RETURN true;
END;
$$ LANGUAGE plpgsql;
```

---

## When to Use JSONB

```
✅ Use JSONB for:
- Flexible attributes (product.variations: {"size": "L", "color": "red"})
- Rarely queried data
- Schema-adjacent features (user.preferences)
- Prototype/rapid development

❌ Don't use JSONB for:
- Core business data (orders, products)
- Data you need to JOIN on
- Data you need to aggregate/sum
- Foreign key relationships
```

---

## Index Strategy

```sql
-- B-tree for equality and range
CREATE INDEX orders_user ON orders(user_id);
CREATE INDEX orders_created ON orders(created_at DESC);

-- Composite for multi-column queries
CREATE INDEX orders_user_status ON orders(user_id, status);

-- Partial for filtered queries
CREATE INDEX orders_active ON orders(id) WHERE status != 'cancelled';

-- GIN for JSONB (if you must query it)
CREATE INDEX products_metadata ON products USING GIN (metadata);
-- Example: WHERE metadata @> '{"featured": true}'

-- Unique for constraints
CREATE UNIQUE INDEX users_email ON users(email);
CREATE UNIQUE INDEX users_username ON users(username);
```

---

**Now read `solution.md` for complete reference.**
