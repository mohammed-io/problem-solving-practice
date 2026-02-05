# Step 2: Defense Layers

---

## Multi-Layer Rate Limiting

```go
package main

import (
    "context"
    "fmt"
    "net/http"
    "time"

    "github.com/redis/go-redis/v9"
)

// Layer 1: IP-based (for anonymous)
func IPLimiter() *RateLimiter {
    return NewSlidingWindowLimiter(
        1000,              // requests
        time.Minute,       // per minute
        func(r *http.Request) string {
            return r.RemoteAddr
        },
    )
}

// Layer 2: Account-based (for authenticated)
func AccountLimiter() *RateLimiter {
    return NewTokenBucket(
        100,                // requests
        time.Minute,        // per minute
        func(r *http.Request) string {
            // Get user ID from JWT, not header!
            userID := getUserIDFromContext(r.Context())
            return fmt.Sprintf("account:%s", userID)
        },
    )
}

// Layer 3: Global (protect infrastructure)
func GlobalLimiter() *RateLimiter {
    return NewLeakyBucket(
        100000,             // Total requests
        time.Second,        // per second
        func(r *http.Request) string {
            return "global"
        },
    )
}

type RateLimitMiddleware struct {
    ip      *RateLimiter
    account *RateLimiter
    global  *RateLimiter
}

func (m *RateLimitMiddleware) Handler(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        // Check global limit first
        if !m.global.Allow(r) {
            http.Error(w, "Rate limit exceeded (global)", http.StatusTooManyRequests)
            return
        }

        // Check account limit if authenticated
        userID := getUserIDFromContext(r.Context())
        if userID != "" {
            if !m.account.Allow(r) {
                http.Error(w, "Rate limit exceeded (account)", http.StatusTooManyRequests)
                return
            }
        } else {
            // Check IP limit for anonymous
            if !m.ip.Allow(r) {
                http.Error(w, "Rate limit exceeded (IP)", http.StatusTooManyRequests)
                return
            }
        }

        next.ServeHTTP(w, r)
    })
}
```

---

## Redis-Based Distributed Rate Limiting

```go
package main

import (
    "context"
    "fmt"
    "time"

    "github.com/redis/go-redis/v9"
)

type RedisRateLimiter struct {
    client *redis.Client
}

func (r *RedisRateLimiter) Allow(ctx context.Context, key string, limit int, window time.Duration) bool {
    now := time.Now().Unix()
    windowStart := now - int64(window.Seconds())

    pipe := r.client.Pipeline()

    // Add current request
    pipe.ZAdd(ctx, key, redis.Z{
        Score:  float64(now),
        Member: now,
    })

    // Remove old requests
    pipe.ZRemRangeByScore(ctx, key, "0", fmt.Sprint(windowStart))

    // Count current window
    countCmd := pipe.ZCard(ctx, key)

    _, err := pipe.Exec(ctx)
    if err != nil {
        return false  // Fail closed
    }

    current := countCmd.Val()
    return current <= int64(limit)
}

// Usage:
func handler(w http.ResponseWriter, req *http.Request) {
    userID := getUserIDFromToken(req)
    key := fmt.Sprintf("ratelimit:user:%s", userID)

    limiter := &RedisRateLimiter{client: redisClient}
    if !limiter.Allow(req.Context(), key, 100, time.Minute) {
        http.Error(w, "Rate limit exceeded", http.StatusTooManyRequests)
        return
    }

    // Process request...
}
```

---

## Device Fingerprinting

```go
package main

import (
    "crypto/sha256"
    "encoding/hex"
    "fmt"
    "strings"
)

// Generate device fingerprint from request attributes
func DeviceFingerprint(r *http.Request) string {
    var components []string

    // User-Agent
    components = append(components, r.UserAgent())

    // Accept headers (can indicate browser type)
    components = append(components, r.Header.Get("Accept"))
    components = append(components, r.Header.Get("Accept-Encoding"))
    components = append(components, r.Header.Get("Accept-Language"))

    // Screen resolution (if available from JS)
    // This would come from a cookie or header set by client-side JS

    data := strings.Join(components, "|")
    hash := sha256.Sum256([]byte(data))
    return hex.EncodeToString(hash[:])
}

// Rate limiter using device fingerprint
func DeviceLimiter() *RateLimiter {
    return NewSlidingWindowLimiter(
        50,                 // requests
        time.Minute,        // per minute
        func(r *http.Request) string {
            device := DeviceFingerprint(r)
            return fmt.Sprintf("device:%s", device)
        },
    )
}
```

---

## Honeytoken Detection

```go
package main

// Honeytoken: Fake user IDs that trigger rate limiting
var honeytokens = map[string]bool{
    "usr_honey_001": true,
    "usr_honey_002": true,
}

// If user provides honeytoken, ban immediately
func CheckHoneytoken(userID string) bool {
    if honeytokens[userID] {
        // Log the attempt, ban IP, etc.
        log.Printf("Honeytoken used: %s", userID)
        BanIP(GetIPFromContext())
        return true
    }
    return false
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. Why use multi-layer rate limiting? (Single layer can be bypassed; IP + account + device + global provides defense in depth)
2. Why use Redis for distributed rate limiting? (Shared state across all instances, atomic operations, scalable)
3. What's device fingerprinting? (Generate hash from client attributes like User-Agent, accept headers, screen resolution)
4. How do honeytokens help? (Fake credentials that trigger detection when used; identify attackers early)
5. Why get user ID from JWT not header? (Headers can be spoofed; JWT is cryptographically signed by server)

---

**Read `solution.md`**
