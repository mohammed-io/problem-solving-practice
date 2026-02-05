# Solution: Rate Limiter

---

## Good Approach: Redis Sliding Window

```go
type RateLimiter struct {
    redis *redis.Client
}

func (rl *RateLimiter) Allow(apiKey string, limit int, window time.Duration) bool {
    key := fmt.Sprintf("ratelimit:%s", apiKey)

    // Get current count
    count, _ := rl.redis.Incr(key).Result()

    if count == 1 {
        // First request, set expiration
        rl.redis.Expire(key, window)
    }

    return count <= limit
}
```

**Why this works:**
- Redis is shared across all API servers
- `INCR` is atomic (no race conditions)
- `EXPIRE` automatically resets counter

---

## Better: Sliding Window Log

```go
func (rl *RateLimiter) Allow(apiKey string) bool {
    key := fmt.Sprintf("ratelimit:%s", apiKey)
    now := time.Now().Unix()
    window := 60  // 60 seconds

    pipe := rl.redis.Pipeline()

    // Remove old entries outside window
    pipe.ZRemRangeByScore(key, "0", fmt.Sprintf("%d", now-60))

    // Add current request
    pipe.ZAdd(key, &redis.Z{Score: float64(now), Member: now})

    // Count requests in window
    cmdCount := pipe.ZCard(key)

    // Set expiration (cleanup)
    pipe.Expire(key, 70*time.Second)

    _, _ = pipe.Exec()

    return cmdCount.Val() < 100
}
```

---

## Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| **In-memory** | Fast | Not distributed, resets on restart |
| **Redis (fixed window)** | Simple, distributed | Bursts at window boundaries |
| **Redis (sliding window)** | Smooth | More memory, slightly slower |
| **Token bucket** | Allows bursts | More complex |

**Recommended:** Redis sliding window for distributed systems.

---

## Jargon

| Term | Definition |
|------|------------|
| **Rate limiting** | Limiting request rate per user/API key |
| **Sliding window** | Counting requests in rolling time window |
| **Fixed window** | Counting requests in fixed time buckets (e.g., per minute) |
| **Token bucket** | Algorithm allowing bursts with steady refill |
| **Atomic operation** | Operation that completes fully or not at all; no interleaving |
