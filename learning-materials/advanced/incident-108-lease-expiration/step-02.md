# Step 2: Fencing Tokens and Clock Skew

---

## Fencing Token Solution

Each lease renewal includes a monotonically increasing token:

```go
type Lease struct {
    Key       string
    Holder    string
    Token     int64   // Monotonic: increases each lease
    ExpiresAt time.Time
}

func AcquireLease(key, holder string, ttl time.Duration) (int64, error) {
    script := `
        local key = KEYS[1]
        local holder = ARGV[1]
        local ttl = ARGV[2]

        local current = redis.call("GET", key)
        local token = 0
        if current then
            local data = cjson.decode(current)
            if data.expiry > tonumber(ARGV[3]) then
                return {err = "HELD"}  -- Still valid
            end
            token = data.token + 1  -- Increment token
        else
            token = 1
        end

        local lease = {
            holder = holder,
            token = token,
            expiry = tonumber(ARGV[3]) + ttl
        }
        redis.call("SET", key, cjson.encode(lease))
        return token
    `

    result, err := redis.Eval(ctx, script, []string{"lease:" + key},
        holder, ttl.Seconds(), time.Now().Unix()).Result()

    return result.(int64), err
}

// All operations must include fencing token
func WriteWithFencing(key, value string, token int64) error {
    currentToken := getCurrentLeaseToken(key)
    if token < currentToken {
        return ErrStaleToken  // Old leaseholder!
    }
    return storage.Write(key, value)
}
```

---

## Clock Skew Mitigation

```go
// Use hybrid logical time (not wall clock!)
type HLC struct {
    physical int64  // Unix timestamp
    logical  int64  // Counter for same physical time
}

func (h *HLC) Now() int64 {
    physical := time.Now().UnixNano() / 1e6
    h.logical = max(h.logical+1, 0)
    if physical > h.physical {
        h.physical = physical
        h.logical = 0
    }
    return h.physical*1e6 + h.logical
}

// Use HLC for lease expiry
type Lease struct {
    Key      string
    Holder   string
    Token    int64
    ExpireAt HLC  // Not wall clock!
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What is a fencing token? (Monotonic value increasing with each lease)
2. How do fencing tokens prevent stale writes? (Include with operations, reject stale)
3. What is clock skew? (Different servers have different wall clock times)
4. Why is wall clock unreliable for leases? (Clocks drift, NTP jumps)
5. What is HLC? (Hybrid Logical Clock - physical + logical time)

---

**Continue to `solution.md`**
