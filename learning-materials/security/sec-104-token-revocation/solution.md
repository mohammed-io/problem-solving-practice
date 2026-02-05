# Solution: Token Revocation

---

## Root Cause

JWTs are stateless by design; can't revoke without adding state.

---

## Solution

**Hybrid approach: Short-lived JWT + refresh tokens in DB**

```
Access token (JWT):
- 15 minute lifetime
- Contains user ID, token version
- Stateless validation

Refresh token:
- 30 day lifetime
- Stored in database
- Can be revoked immediately

Revocation:
1. Delete refresh tokens
2. Increment token_version
3. Access tokens expire in 15 min max
```

---

## Quick Checklist

- [ ] Access token lifetime < 15 minutes
- [ ] Refresh tokens stored in database
- [ ] Token version checked on each request
- [ ] Revoke endpoint deletes refresh + increments version
- [ ] Refresh token rotation on use

---

**Next Problem:** `performance/perf-101-memory-fragmentation/`
