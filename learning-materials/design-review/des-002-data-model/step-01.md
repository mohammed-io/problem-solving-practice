# Step 1: Data Model Issues

---

## Problems Identified

**1. Data Redundancy**
```
items in orders (JSONB) AND order_items table
→ Can diverge
→ Double storage
→ Confusion about source of truth
```

**2. Unconstrained Status**
```
status: VARCHAR
→ Can insert 'shipeed' (typo)
→ Can't enforce state machine
→ Can't prevent invalid transitions

Solution: ENUM or separate status table
```

**3. Missing Composite Index**
```
Query: WHERE user_id = ? AND status = 'pending'
Index: orders(user_id), orders(status) separately
→ Can't use both efficiently

Solution: CREATE INDEX orders_user_status (user_id, status)
```

**4. JSONB for Queryable Data**
```
items: JSONB makes it hard to:
- Find all orders with specific product
- Aggregate quantities
- Join with products table

Rule: JSONB for rarely queried, flexible data
Structured columns for queried data
```

---

**Read `solution.md`
