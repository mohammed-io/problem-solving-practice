# Step 02: Implementing Rate Limiting

---

## Implementation Approaches

### Approach 1: In-Memory (Single Server)

```python
from collections import deque
import time

class RateLimiter:
    def __init__(self, limit, window):
        self.limit = limit      # e.g., 100 requests
        self.window = window    # e.g., 60 seconds
        self.requests = {}      # client_id -> deque of timestamps

    def is_allowed(self, client_id):
        now = time.time()

        # Clean old requests
        if client_id not in self.requests:
            self.requests[client_id] = deque()
            return True

        # Remove timestamps outside window
        while self.requests[client_id] and self.requests[client_id][0] < now - self.window:
            self.requests[client_id].popleft()

        # Check limit
        if len(self.requests[client_id]) < self.limit:
            self.requests[client_id].append(now)
            return True

        return False
```

**Problem:** Doesn't scale across servers.

---

### Approach 2: Redis (Distributed)

```python
import redis
import time

class RedisRateLimiter:
    def __init__(self, redis_client, limit, window):
        self.redis = redis_client
        self.limit = limit
        self.window = window

    def is_allowed(self, client_id):
        key = f"ratelimit:{client_id}"
        now = time.time()

        # Use Redis sorted set for sliding window
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - self.window)  # Remove old
        pipe.zcard(key)  # Count current
        pipe.zadd(key, {str(now): now})  # Add current
        pipe.expire(key, self.window)  # Auto-cleanup
        results = pipe.execute()

        count = results[1]
        return count < self.limit
```

---

### Approach 3: Token Bucket with Redis

```python
class TokenBucketRateLimiter:
    def __init__(self, redis_client, rate, capacity):
        self.redis = redis_client
        self.rate = rate        # tokens per second
        self.capacity = capacity  # max tokens

    def is_allowed(self, client_id):
        key = f"tokenbucket:{client_id}"
        now = time.time()

        # Get current state
        pipe = self.redis.pipeline()
        pipe.get(f"{key}:tokens")
        pipe.get(f"{key}:last_refill")
        tokens, last_refill = pipe.execute()

        # Initialize if not exists
        if tokens is None:
            tokens = self.capacity
            last_refill = now
        else:
            tokens = float(tokens)
            last_refill = float(last_refill)

        # Refill tokens
        elapsed = now - last_refill
        tokens = min(self.capacity, tokens + elapsed * self.rate)

        # Check if token available
        if tokens >= 1:
            tokens -= 1
            self.redis.set(f"{key}:tokens", tokens)
            self.redis.set(f"{key}:last_refill", now)
            return True

        return False
```

---

## Response Headers

Inform clients about their rate limit status:

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1705334400

HTTP/1.1 429 Too Many Requests
Retry-After: 30
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
```

---

## Best Practices

1. **Rate limit by multiple keys:**
   - IP address (prevent DDoS)
   - User ID (per-user limits)
   - API key (per-application limits)

2. **Different limits for different endpoints:**
   ```python
   limits = {
       '/api/search': (100, 60),      # 100/min
       '/api/posts': (10, 60),        # 10/min
       '/api/auth/login': (5, 300),   # 5/5min
   }
   ```

3. **Use middleware:**
   ```python
   @app.middleware("http")
   async def rate_limit_middleware(request, call_next):
       if not rate_limiter.is_allowed(request.client.host):
           return JSONResponse(
               {"error": "Rate limit exceeded"},
               status_code=429
           )
       return await call_next(request)
   ```

---

## Summary

| Approach | Pros | Cons | Use Case |
|----------|------|------|----------|
| In-memory | Fast, simple | Single-server only | Development |
| Redis sliding window | Accurate | O(n) memory | Strict limits |
| Redis token bucket | Burst-friendly | Slightly complex | General APIs |
| Leaky bucket | Smooth traffic | Delayed requests | Streaming |

---

**Now read `solution.md` for complete implementation.**
