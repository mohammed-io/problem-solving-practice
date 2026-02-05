# Step 2: Complete API Design

---

## Improved API Specification

```
# User Profile API v2

## Authentication
- OAuth2 Bearer tokens
- Scopes: read:profile, write:profile, read:email
- Rate limiting: Per-endpoint (not global)

## Endpoints

### Get User Profile
GET /api/v2/users/:id

Authorization: Bearer <token>

Response:
{
  "id": "123",
  "username": "johndoe",
  "bio": "Software engineer",
  "avatar_url": "https://...",
  "follower_count": 1000,
  "created_at": "2024-01-01T00:00:00Z"
}

With email scope:
{
  ...,
  "email": "john@example.com"  // Only with email scope
}

### List Users (with pagination)
GET /api/v2/users?cursor=<base64>&limit=50&status=active&sort=created_at:desc

Response:
{
  "data": [...],
  "pagination": {
    "next_cursor": "eyJpZCI6MTIzfQ==",
    "has_more": true
  }
}

### Update User (partial)
PATCH /api/v2/users/:id

Authorization: Bearer <token>
Scope: write:profile

Body: {"bio": "New bio"}

Response: 200 OK with updated user

Headers:
ETag: "33a64df551425fcc55e4d42a148795d9f25f89d4"

Idempotency-Key: <uuid>
```

---

## Error Responses

```
400 Bad Request
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "Username must be 3-30 characters",
    "details": {"field": "username", "value": "ab"}
  }
}

401 Unauthorized
{
  "error": {
    "code": "INVALID_TOKEN",
    "message": "Expired or invalid token"
  }
}

403 Forbidden
{
  "error": {
    "code": "INSUFFICIENT_SCOPE",
    "message": "Email scope required",
    "required_scopes": ["read:email"]
  }
}

404 Not Found
{
  "error": {
    "code": "USER_NOT_FOUND",
    "message": "User not found"
  }
}

429 Too Many Requests
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded",
    "retry_after": 60
  }
}
```

---

## API Versioning Strategy

```
URL versioning: /api/v1/, /api/v2/
- Clear, explicit version
- Easy to deprecate old versions
- Client controls version

Alternative: Header versioning
Accept: application/vnd.api.v2+json

Choose: URL versioning (simpler for clients)
```

---

## Idempotency

```
POST /api/v2/users
Idempotency-Key: <uuid>

Same key = same result
Client can retry safely

DELETE /api/v2/users/:id
Always idempotent (deleting already deleted = 404, but idempotent)

PATCH /api/v2/users/:id
Idempotent if same payload
```

---

## Webhooks (Optional)

```
POST /api/v2/webhooks

Subscribe to user events:
{
  "url": "https://your-server.com/webhooks",
  "events": ["user.updated", "user.deleted"],
  "secret": "webhook_secret"
}

Webhook delivery:
POST <url>
X-Webhook-Signature: sha256=<hmac>
X-Webhook-Event: user.updated
{
  "event": "user.updated",
  "data": {...}
}
```

---

**Now read `solution.md` for complete reference.**
