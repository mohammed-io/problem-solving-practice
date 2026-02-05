---
name: design-003-rate-limiter
description: Rate Limiter
difficulty: Basic
category: System Design
level: Junior to Mid-level
---
# Design 003: Rate Limiter

---

## The Requirement

Design a rate limiter for a public API:

**Requirements:**
- Limit each API key to 100 requests per minute
- Return HTTP 429 (Too Many Requests) when limit exceeded
- Distributed system (multiple API servers)

**What is a Rate Limiter?**

Imagine a nightclub with a bouncer. The bouncer lets in 100 people per minute. If 101 people try to enter, the bouncer says "Sorry, you need to wait."

**In API terms:** Prevent any one user from overwhelming your API.

---

## Questions

1. **Where does the rate limiter sit?** (Client? API Gateway? Application?)

2. **How do you track request counts?** (In-memory? Redis? Database?)

3. **What happens when a limit is hit?** (Return error? Queue requests?)

4. **How do you handle distributed systems?** (Multiple servers counting for same user)

5. **What are the edge cases?** (Burst requests, clock drift)

---

## Simple Approach

```go
// In-memory map (NOT distributed)
type RateLimiter struct {
    requests map[string]int  // API key → count
    mu       sync.Mutex
}

func (rl *RateLimiter) Allow(apiKey string) bool {
    rl.mu.Lock()
    defer rl.mu.Unlock()

    if rl.requests[apiKey] >= 100 {
        return false
    }

    rl.requests[apiKey]++
    return true
}
```

**What's wrong with this?**

1. Counts never reset (100 requests ever, not per minute)
2. Not distributed (each API server has its own counter)
3. No cleanup (memory leak as users accumulate)

---

**When you have ideas, read `solution.md`**
