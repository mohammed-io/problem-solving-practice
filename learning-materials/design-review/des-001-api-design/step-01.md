# Step 1: API Design Analysis

---

## Issues Found

**1. Data Exposure**
```
GET /api/users/:id returns email
  - PII exposure
  - Should be opt-in or require authorization
  - Consider scopes: public vs private fields
```

**2. No Pagination**
```
GET /api/users returns ALL users
  - Will break as users grow
  - Memory exhaustion
  - Slow response time

Solution: Add pagination
  GET /api/users?page=1&limit=50
  Or cursor-based for large datasets
```

**3. Non-Idempotent POST**
```
POST /api/users/:id
  - POST should create, not update
  - Should use PATCH or PUT
  - PUT for full replace, PATCH for partial update
```

---

## Better Design

```
# User Profile API v1

GET /api/v1/users/:id
  Returns: Public profile only
  Fields: id, name, bio, avatar_url

PATCH /api/v1/users/:id
  Updates: Specific fields
  Body: {"field": "value"}
  Idempotent: Yes

GET /api/v1/users
  Pagination: ?cursor=xxx&limit=50
  Filtering: ?status=active&tier=pro
  Sorting: ?sort=created_at:desc

Authentication: Bearer token (OAuth2)
Rate limiting: Per-endpoint, not global
```

---

**Read `solution.md`**
