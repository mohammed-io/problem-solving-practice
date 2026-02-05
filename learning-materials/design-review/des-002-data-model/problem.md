---
name: des-002-data-model
description: System design problem
difficulty: Advanced
category: Design Review / Database / Staff Engineer
level: Staff Engineer
---
# Design Review 002: Data Model Review

---

## The Design Document

```
# Order Processing Schema

Table: orders
  id: UUID (PK)
  user_id: UUID
  items: JSONB [{"product_id": "xxx", "qty": 1, ...}]
  status: VARCHAR (pending, processing, shipped, delivered)
  created_at: TIMESTAMP
  updated_at: TIMESTAMP

Table: order_items (redundant!)
  order_id: UUID (FK)
  product_id: UUID
  quantity: INT
  price: DECIMAL

Indexes:
  - orders(user_id)
  - orders(status)
  - order_items(order_id)
  - order_items(product_id)

Query example:
  SELECT * FROM orders
  WHERE user_id = ? AND status = 'pending'
  ORDER BY created_at DESC
```

---

## Your Review

Identify issues with this data model.

---

## Concerns

1. **Redundancy**: Items stored twice (JSONB + table)?

2. **Status**: VARCHAR allows invalid states

3. **Query**: No index on (user_id, status) composite

4. **JSONB**: Can't efficiently query items

5. **Transactions**: Updating orders + items?

6. **Migration**: How to change JSON schema?

---

**Read `step-01.md`
