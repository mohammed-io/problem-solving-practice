# Solution: Rate Limiting

---

## Root Cause

Rate limit keyed off client-controlled header (X-User-ID), allowing rotation.

---

## Solution

**Use authenticated identity + multiple layers:**

```go
// Don't trust client headers
func getUserID(r *http.Request) string {
    token := r.Header.Get("Authorization")
    claims, _ := validateJWT(token)  // Verify signature
    return claims.UserID  // From verified token
}

// Apply all layers
func RateLimitMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        // Global limit (protect infrastructure)
        if !globalLimiter.Allow() {
            http.Error(w, "System overloaded", 503)
            return
        }

        // IP limit (for anonymous/bot detection)
        if !ipLimiter.Allow(r) {
            http.Error(w, "IP rate limited", 429)
            return
        }

        // Account limit (for authenticated users)
        if userID := getUserID(r); userID != "" {
            if !accountLimiter.Allow(userID) {
                http.Error(w, "Account rate limited", 429)
                return
            }
        }

        next.ServeHTTP(w, r)
    })
}
```

---

**Next Problem:** `security/sec-104-token-revocation/`
