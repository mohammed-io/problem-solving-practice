# Solution: Cursor Pagination - Performance at Any Depth

---

## Root Cause

**OFFSET requires scanning all previous rows**, even with index. Performance degrades linearly with page number.

---

## Complete Solution

### Cursor Pagination Implementation

```go
type PaginationRequest struct {
    Limit  int
    Cursor string  // Encoded tuple of (sort_col1, sort_col2, ...)
}

type PaginationResponse struct {
    Data       []Order
    NextCursor string
    HasMore    bool
}

type Cursor struct {
    Status    string
    CreatedAt time.Time
    ID        int64
}

func (r *Repository) ListOrders(ctx context.Context, req PaginationRequest) (*PaginationResponse, error) {
    const defaultLimit = 100
    limit := req.Limit
    if limit <= 0 || limit > 1000 {
        limit = defaultLimit
    }

    var cursor Cursor
    var whereClause string
    var args []interface{}

    if req.Cursor != "" {
        var err error
        cursor, err = decodeCursor(req.Cursor)
        if err != nil {
            return nil, err
        }
        whereClause = fmt.Sprintf(
            "WHERE (status, created_at, id) > ($1, $2, $3)",
        )
        args = []interface{}{cursor.Status, cursor.CreatedAt, cursor.ID}
    }

    query := fmt.Sprintf(`
        SELECT id, user_id, status, created_at
        FROM orders
        %s
        ORDER BY status, created_at, id
        LIMIT $%d
    `, whereClause, len(args)+1)

    args = append(args, limit+1)  // Fetch one extra to check has_more

    rows, err := r.db.QueryContext(ctx, query, args...)
    if err != nil {
        return nil, err
    }
    defer rows.Close()

    var orders []Order
    for rows.Next() {
        var o Order
        if err := rows.Scan(&o.ID, &o.UserID, &o.Status, &o.CreatedAt); err != nil {
            return nil, err
        }
        orders = append(orders, o)
    }

    hasMore := len(orders) > limit
    if hasMore {
        orders = orders[:limit]  // Remove extra
    }

    var nextCursor string
    if len(orders) > 0 {
        lastOrder := orders[len(orders)-1]
        nextCursor = encodeCursor(Cursor{
            Status:    lastOrder.Status,
            CreatedAt: lastOrder.CreatedAt,
            ID:        lastOrder.ID,
        })
    }

    return &PaginationResponse{
        Data:       orders,
        NextCursor: nextCursor,
        HasMore:    hasMore,
    }, nil
}

func encodeCursor(c Cursor) string {
    // Base64 encode to handle special characters
    data := fmt.Sprintf("%s|%s|%d", c.Status, c.CreatedAt.UnixNano(), c.ID)
    return base64.StdEncoding.EncodeToString([]byte(data))
}

func decodeCursor(s string) (Cursor, error) {
    data, err := base64.StdEncoding.DecodeString(s)
    if err != nil {
        return Cursor{}, err
    }

    parts := strings.Split(string(data), "|")
    if len(parts) != 3 {
        return Cursor{}, errors.New("invalid cursor")
    }

    ts, _ := strconv.ParseInt(parts[1], 10, 64)
    id, _ := strconv.ParseInt(parts[2], 10, 64)

    return Cursor{
        Status:    parts[0],
        CreatedAt: time.Unix(0, ts),
        ID:        id,
    }, nil
}
```

### Supporting Previous Page

```go
func (r *Repository) ListOrdersPrev(ctx context.Context, cursor string, limit int) (*PaginationResponse, error) {
    // For previous page, we use reverse ordering with < instead of >
    query := `
        SELECT id, user_id, status, created_at
        FROM orders
        WHERE (status, created_at, id) < ($1, $2, $3)
        ORDER BY status DESC, created_at DESC, id DESC
        LIMIT $4
    `

    // ... execute query ...

    // Reverse results to maintain order
    for i, j := 0, len(orders)-1; i < j; i, j = i+1, j-1 {
        orders[i], orders[j] = orders[j], orders[i]
    }

    return response, nil
}
```

### Filtering with Cursors

```go
// Adding filters while maintaining cursor pagination
func (r *Repository) ListOrdersFiltered(ctx context.Context, req PaginationRequest, filters Filters) (*PaginationResponse, error) {
    whereClause := "WHERE 1=1"
    args := []interface{}{}

    if filters.Status != "" {
        whereClause += " AND status = $" + strconv.Itoa(len(args)+1)
        args = append(args, filters.Status)
    }

    if !filters.FromDate.IsZero() {
        whereClause += " AND created_at >= $" + strconv.Itoa(len(args)+1)
        args = append(args, filters.FromDate)
    }

    // Add cursor condition last
    if req.Cursor != "" {
        cursor, _ := decodeCursor(req.Cursor)
        // Filter must be compatible with cursor ordering
        whereClause += fmt.Sprintf(" AND (created_at, id) > ($%d, $%d)", len(args)+1, len(args)+2)
        args = append(args, cursor.CreatedAt, cursor.ID)
    }

    // ... rest of implementation
}
```

---

## Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| **OFFSET** | Simple, supports any page | Slow at depth, O(n) |
| **Cursor** | O(1) at any depth | No random page access |
| **Seek (cursor + batch size)** | Good for infinite scroll | Can't jump to page |

**Recommendation:** Cursor pagination for large datasets, API endpoints. OFFSET acceptable for small, paginated admin views (<1000 total rows).

---

**Next Problem:** `advanced/postgres-105-write-skew/`
