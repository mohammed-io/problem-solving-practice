# Step 1: Basic Cursor Pagination

---

## The Transformation

**Before (OFFSET):**
```sql
SELECT * FROM orders
ORDER BY id
LIMIT 100 OFFSET 999900;
```

**After (CURSOR):**
```sql
SELECT * FROM orders
WHERE id > 999900  -- Start from last seen ID
ORDER BY id
LIMIT 100;
```

**Performance:**
- Before: Scans 1,000,000 rows
- After: Scans 100 rows

**100x faster!**

---

## API Response Structure

```json
{
  "data": [...],
  "pagination": {
    "next_cursor": "100050",
    "has_more": true
  }
}
```

**Usage:**
```
GET /orders?limit=100
→ Returns first 100, next_cursor="100"

GET /orders?limit=100&cursor=100
→ Returns next 100, next_cursor="200"

GET /orders?limit=100&cursor=100
→ Always consistent, no matter when called
```

---

## Quick Check

Before moving on, make sure you understand:

1. Why is OFFSET slow? (Scans and skips all previous rows)
2. How does cursor pagination work? (WHERE id > last_seen_id instead of OFFSET)
3. Why is cursor faster? (Uses index, doesn't scan skipped rows)
4. What's the API response structure? (data array + next_cursor)
5. Why is cursor pagination consistent? (Same cursor always returns same results)

---

**Continue to `step-02.md`**
