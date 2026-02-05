# Step 1: The Renewal Race

---

## The Race Timeline

```
Storage state at each time:

T-5:  Holder=A, Expires=T+30
T-2:  [A sends renew] in flight
T:    Expires=T (actually T+30 based on last renew)
T+1:  Expires=T (EXPIRED!)
      [B sees expired, acquires]
T+1:  Holder=B, Expires=T+31
T+5:  [A's renew arrives!]
      Overwrites: Holder=A, Expires=T+35
```

**Problem:** Renewal doesn't check if lease was reassigned after expiration!

---

## The Fix: Conditional Renewal

```go
// RIGHT: Atomic check-and-set
func RenewLease(key, holder string, ttl time.Duration) error {
    script := `
        local key = KEYS[1]
        local holder = ARGV[1]
        local ttl = ARGV[2]
        local expiry = ARGV[3]  -- Current expiry we expect

        local lease = redis.call("GET", key)
        if not lease then
            return "EXPIRED"
        end

        local data = cjson.decode(lease)
        if data.holder ~= holder then
            return "NOT_HOLDER"
        end

        if data.expiry < tonumber(expiry) then
            return "EXPIRED"  -- Already expired and possibly reassigned
        end

        -- Still our lease, safe to renew
        data.expiry = tonumber(expiry) + ttl
        redis.call("SET", key, cjson.encode(data))
        return "OK"
    `

    result, err := redis.Eval(ctx, script, []string{"lease:" + key},
        holder, ttl.Seconds(), time.Now().Unix()).Result()

    if result == "EXPIRED" {
        return ErrLeaseExpired  // Must re-acquire, not renew!
    }

    return nil
}
```

**Key insight:** Include expected expiry in renewal. If expiry doesn't match, someone else acquired lease.

---

## Quick Check

Before moving on, make sure you understand:

1. What is the renewal race? (Renewal arrives after reassignment)
2. Why does unconditional renewal fail? (Doesn't check if lease was reassigned)
3. What's conditional renewal? (Check holder AND expected expiry)
4. How does expected expiry help? (Detects if lease was reassigned after expiry)
5. What should happen on ErrLeaseExpired? (Must re-acquire, not renew)

---

**Continue to `step-02.md`**
