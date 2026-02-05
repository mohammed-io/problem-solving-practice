# Step 2: Complex Sorting and Edge Cases

---

## Sorting by Non-Unique Column

```
Problem: Multiple orders can have same created_at

Bad:
SELECT * FROM orders
WHERE created_at > '2024-01-01 10:00:00'  -- Duplicate timestamps!
ORDER BY created_at
LIMIT 100;

→ Might skip or duplicate rows!
```

**Solution: Use tuple comparison**

```sql
SELECT * FROM orders
WHERE (created_at, id) > ('2024-01-01 10:00:00', 12345)
ORDER BY created_at, id
LIMIT 100;
```

**Why this works:** `(created_at, id)` is unique even if `created_at` isn't. The comparison works lexicographically.

---

## Multiple Sort Columns

```
API: /orders?sort=status&sort=created_at&sort=id

Client wants: ORDER BY status, created_at, id

Cursor must include all sort columns:
WHERE (status, created_at, id) > ('pending', '2024-01-01 10:00:00', 12345)
ORDER BY status, created_at, id
LIMIT 100;
```

---

## Bidirectional Pagination

```json
{
  "data": [...],
  "pagination": {
    "next_cursor": "pending|2024-01-01T10:00:00|100050",
    "prev_cursor": "pending|2024-01-01T09:00:00|999950",
    "has_more": true
  }
}
```

**Encode cursor:** Values for all sort columns, pipe-separated

```go
type Cursor struct {
    Status    string
    CreatedAt time.Time
    ID        int64
}

func EncodeCursor(c Cursor) string {
    return fmt.Sprintf("%s|%s|%d", c.Status, c.CreatedAt.Format(time.RFC3339), c.ID)
}

func DecodeCursor(s string) (Cursor, error) {
    parts := strings.Split(s, "|")
    createdAt, _ := time.Parse(time.RFC3339, parts[1])
    id, _ := strconv.ParseInt(parts[2], 10, 64)
    return Cursor{Status: parts[0], CreatedAt: createdAt, ID: id}, nil
}

// Next page query
func NextPageQuery(cursor Cursor) string {
    return fmt.Sprintf(
        "WHERE (status, created_at, id) > ('%s', '%s', %d) ORDER BY status, created_at, id LIMIT 100",
        cursor.Status, cursor.CreatedAt.Format(time.RFC3339Nano), cursor.ID,
    )
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's the problem with sorting by non-unique columns? (Can skip or duplicate rows)
2. How do tuple cursors solve this? ((col1, col2, id) makes sort key unique)
3. How do you encode cursers with multiple columns? (Pipe-separated or base64 encoded values)
4. What's bidirectional pagination? (Both next and prev cursors)
5. Why does tuple comparison work lexicographically? ((a, b) > (c, d) compares a first, then b)

---

**Continue to `solution.md`**
