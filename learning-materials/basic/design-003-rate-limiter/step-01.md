# Step 01: Understanding Rate Limiting

---

## What is Rate Limiting?

**Rate limiting** controls how many requests a client can make in a time window.

**Example:** "100 requests per minute per IP"

**Why use it?**
- Prevent abuse (DDoS, brute force)
- Fair resource allocation
- Cost control (API pricing tiers)
- Protect backend services

---

## Common Rate Limiting Algorithms

### 1. Fixed Window

```
Window: 1 minute
Limit: 100 requests

Timeline:
00:00 - 00:59: Request 1-100 ✓
01:00 - 01:59: Request 1-100 ✓

Problem: Double requests at boundary
00:59: 100 requests
01:00: 100 requests
= 200 requests in 1 second!
```

### 2. Sliding Window Log

```
Track each request timestamp:
[00:00, 00:05, 00:10, ...]

For each request:
1. Remove timestamps older than window
2. Count remaining
3. If count < limit: allow

Accurate but expensive (O(n) space).
```

### 3. Token Bucket

```
Bucket holds tokens (capacity = limit)
Refill rate: tokens per second

Request:
- If token available: consume, allow
- If no token: deny

Burst allowed (up to capacity).
```

### 4. Leaky Bucket

```
Bucket holds requests
Leak rate: requests per second

Request:
- If bucket not full: add, allow
- If bucket full: deny

Smooths out traffic.
```

---

## Question: Which Algorithm to Choose?

**Consider:**
- Do you want to allow bursts? (Token bucket)
- Do you want smooth rate? (Leaky bucket)
- Need strict accuracy? (Sliding window log)
- Want simplicity? (Fixed window)

**Most APIs use:** Token bucket or sliding window.

---

**Still thinking? Read `step-02.md`**

---

## Quick Check

Before moving on, make sure you understand:

1. What is rate limiting? (Control how many requests per time window)
2. What's the problem with fixed window? (Double requests at boundary, bursty)
3. How does sliding window log work? (Track timestamps, accurate but expensive)
4. What's token bucket algorithm? (Refill tokens, allow bursts up to capacity)
5. What's leaky bucket algorithm? (Smooth out traffic, constant leak rate)

