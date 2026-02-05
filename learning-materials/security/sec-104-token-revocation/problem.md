---
name: sec-104-token-revocation
description: Token Revocation
difficulty: Advanced
category: Security / JWT / Sessions
level: Senior Engineer
---
# Security 104: Token Revocation

---

## The Situation

You use JWTs for authentication. User reports their account was hacked.

**Your JWT:**
```json
{
  "sub": "user_123",
  "exp": 1735689600,
  "iat": 1735603200,
  "roles": ["admin"]
}
```

Signed with your secret key. Valid for 24 hours.

---

## The Incident

```
09:00 UTC - User's password stolen in phishing attack
09:05 UTC - Attacker logs in, gets JWT
09:10 UTC - User reports "I'm hacked!"
09:15 UTC - You reset user's password

BUT:
09:05 JWT still valid until 09:00 tomorrow!
Attacker has 24 hours of access despite password reset!

You try to invalidate JWT:
- JWTs are stateless → no server-side session to kill
- Signature still valid → tokens still accepted
- Exp hasn't passed → token still good

Attacker continues accessing admin panel for 23+ hours
```

---

## The Problem

**JWTs are designed to be stateless:**
```
Pros:
- No server-side session storage
- Scales horizontally
- Works across microservices

Cons:
- Cannot be revoked before expiration
- Must wait for exp to invalidate
```

---

## Questions

1. **Why can't JWTs be easily revoked?**

2. **What are the revocation strategies?**

3. **Short-lived vs long-lived tokens?**

4. **What's token introspection?**

5. **As a Senior Engineer, how do you handle revocation?**

---

## Jargon

| Term | Definition |
|------|------------|
| **JWT** | JSON Web Token - self-contained token |
| **exp** | Expiration time |
| **iat** | Issued at time |
| **jti** | JWT ID - unique identifier |
| **Revocation** | Invalidating token before expiration |
| **Token Introspection** | Checking if token is valid |
| **Refresh Token** | Long-lived token to get new access tokens |
| **Blocklist** | List of revoked tokens |

---

**Read `step-01.md`**
