# Solution: Data Model Review

---

## Improved Design

```
# Order Processing Schema (Improved)

Table: orders
  id: UUID (PK)
  user_id: UUID (FK → users.id)
  status: order_status (ENUM)
  created_at: TIMESTAMP
  updated_at: TIMESTAMP
  completed_at: TIMESTAMP (nullable)

Table: order_items
  order_id: UUID (FK → orders.id) ON DELETE CASCADE
  product_id: UUID (FK → products.id)
  quantity: INT NOT NULL
  unit_price: DECIMAL NOT NULL  -- Price at order time
  PRIMARY KEY (order_id, product_id)

Type: order_status
  VALUES: ('pending'), ('processing'), ('shipped'), ('delivered'), ('cancelled')

Indexes:
  orders_user_status: (user_id, status)
  orders_created: (created_at DESC)
  order_items_product: (product_id)

Constraints:
  orders_status_check: CHECK (status IN ('pending', 'processing', 'shipped', 'delivered', 'cancelled'))
  order_items_quantity_positive: CHECK (quantity > 0)
```

---

## Design Review Checklist

**Data Integrity:**
- [ ] FK constraints defined
- [ ] CHECK constraints for business rules
- [ ] ENUM for fixed values
- [ ] ON DELETE/UPDATE behavior specified

**Performance:**
- [ ] Composite indexes for common queries
- [ ] No redundant data
- [ ] Index size vs query pattern trade-off

**Evolution:**
- [ ] How to add fields?
- [ ] How to change types?
- [ ] Backward compatibility?

---

**Next Problem:** `design-review/des-003-scaling-strategy/`
