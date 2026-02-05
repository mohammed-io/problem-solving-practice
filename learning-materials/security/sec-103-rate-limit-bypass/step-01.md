# Step 1: Rate Limiting Algorithms

---

## Token Bucket

```
Bucket holds tokens
Each request consumes 1 token
Tokens refill at fixed rate
Empty bucket = rate limited

Pros: Allows bursts
Cons: Can be exploited for burst attacks
```

```go
package main

import "time"

type TokenBucket struct {
    capacity  int64
    tokens    int64
    refillRate int64  // tokens per second
    lastRefill time.Time
}

func NewTokenBucket(capacity, refillRate int64) *TokenBucket {
    return &TokenBucket{
        capacity:   capacity,
        tokens:     capacity,
        refillRate: refillRate,
        lastRefill: time.Now(),
    }
}

func (tb *TokenBucket) Allow() bool {
    tb.refill()

    if tb.tokens > 0 {
        tb.tokens--
        return true
    }
    return false
}

func (tb *TokenBucket) refill() {
    now := time.Now()
    elapsed := now.Sub(tb.lastRefill).Seconds()
    tokensToAdd := int64(elapsed * float64(tb.refillRate))

    tb.tokens = min(tb.capacity, tb.tokens+tokensToAdd)
    tb.lastRefill = now
}
```

---

## Leaky Bucket

```
Bucket fills with requests
Requests leak out at fixed rate
Full bucket = requests dropped

Pros: Smooths traffic, prevents bursts
Cons: Doesn't allow legitimate bursts
```

```go
type LeakyBucket struct {
    capacity   int64
    waterLevel int64
    leakRate   int64  // requests per second
    lastLeak   time.Time
}

func NewLeakyBucket(capacity, leakRate int64) *LeakyBucket {
    return &LeakyBucket{
        capacity:   capacity,
        leakRate:   leakRate,
        lastLeak:   time.Now(),
    }
}

func (lb *LeakyBucket) Allow() bool {
    lb.leak()

    if lb.waterLevel < lb.capacity {
        lb.waterLevel++
        return true
    }
    return false  // Bucket full
}

func (lb *LeakyBucket) leak() {
    now := time.Now()
    elapsed := now.Sub(lb.lastLeak).Seconds()
    leaked := int64(elapsed * float64(lb.leakRate))

    lb.waterLevel = max(0, lb.waterLevel-leaked)
    lb.lastLeak = now
}
```

---

## Sliding Window Log

```
Keep log of all request timestamps
Count requests in last time window
Count > limit = rate limited

Pros: Accurate
Cons: Memory intensive for high traffic
```

```go
type SlidingWindowLog struct {
    window  time.Duration
    limit   int
    requests map[string][]time.Time
    mu      sync.Mutex
}

func NewSlidingWindowLog(window time.Duration, limit int) *SlidingWindowLog {
    return &SlidingWindowLog{
        window:  window,
        limit:   limit,
        requests: make(map[string][]time.Time),
    }
}

func (swl *SlidingWindowLog) Allow(key string) bool {
    swl.mu.Lock()
    defer swl.mu.Unlock()

    now := time.Now()
    windowStart := now.Add(-swl.window)

    // Get or init request log
    log := swl.requests[key]

    // Remove old requests outside window
    var newLog []time.Time
    for _, ts := range log {
        if ts.After(windowStart) {
            newLog = append(newLog, ts)
        }
    }
    swl.requests[key] = newLog

    // Check if under limit
    if len(newLog) < swl.limit {
        swl.requests[key] = append(newLog, now)
        return true
    }
    return false
}
```

---

## The Attacks Explained

**Header rotation:**
```
Your code: r.Header.Get("X-User-ID")
Attacker: Change header arbitrarily
Fix: Use authenticated session, not client-provided value
```

**IP rotation:**
```
Your code: Limit by remote address
Attacker: Use proxy network / botnet
Fix: Multiple layers (IP + account + device fingerprint)
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's the token bucket algorithm? (Fixed capacity refills at constant rate, allows bursts up to capacity)
2. What's the leaky bucket algorithm? (Requests leak at fixed rate, full bucket drops requests, prevents bursts)
3. What's the sliding window log? (Keep all request timestamps, count within window, most accurate but memory intensive)
4. Why is header-based rate limiting vulnerable? (Clients can set arbitrary headers, trivial to bypass)
5. What's IP rotation attack? (Attacker uses proxy network or botnet with many different IPs to bypass per-IP limits)

---

**Read `step-02.md`**
