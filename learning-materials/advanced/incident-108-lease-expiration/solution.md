# Solution: Lease Expiration Race - Fencing and Conditional Renewal

---

## Root Cause

**Two failures:**
1. Renewal doesn't verify lease still held by caller
2. No fencing token to detect stale leaseholders

---

## Complete Solution

### Solution 1: Atomic Check-and-Set Renewal

```go
func (ls *LeaseService) RenewLease(ctx context.Context, key, holder string, ttl time.Duration) (int64, error) {
    script := `
        local key = KEYS[1]
        local holder = ARGV[1]
        local ttl = ARGV[2]
        local expectedToken = tonumber(ARGV[3])

        local current = redis.call("GET", key)
        if not current then
            return {err = "NOT_FOUND"}
        end

        local data = cjson.decode(current)

        -- Check if still holder
        if data.holder ~= holder then
            return {err = "NOT_HOLDER"}
        end

        -- Check if token matches (no one else acquired)
        if data.token ~= expectedToken then
            return {err = "TOKEN_MISMATCH"}
        end

        -- Check if already expired
        if data.expiry < tonumber(ARGV[4]) then
            return {err = "EXPIRED"}
        end

        -- All checks pass: safe to renew
        data.token = data.token + 1
        data.expiry = tonumber(ARGV[4]) + ttl
        redis.call("SET", key, cjson.encode(data))
        redis.call("EXPIRE", key, ttl + 60)

        return {token = data.token}
    `

    result, err := ls.redis.Eval(ctx, script,
        []string{"lease:" + key},
        holder, int(ttl.Seconds()), ls.lastSeenToken[key],
        time.Now().Unix()).Result()

    if err != nil {
        return 0, err
    }

    resultMap := result.(map[string]interface{})
    if errMsg, ok := resultMap["err"]; ok {
        return 0, errors.New(errMsg.(string))
    }

    token := int64(resultMap["token"].(float64))
    ls.lastSeenToken[key] = token
    return token, nil
}
```

### Solution 2: Fencing Token Enforcement

```go
type FencedClient struct {
    leaseService *LeaseService
    holderID     string
    currentToken int64
}

func (fc *FencedClient) AcquireLease(ctx context.Context, resource string) error {
    token, err := fc.leaseService.AcquireLease(ctx, resource, fc.holderID, 30*time.Second)
    if err != nil {
        return err
    }
    fc.currentToken = token
    return nil
}

func (fc *FencedClient) DoWrite(ctx context.Context, resource string, op WriteOperation) error {
    token, err := fc.leaseService.RenewLease(ctx, resource, fc.holderID, 30*time.Second)
    if err != nil {
        return err
    }
    fc.currentToken = token

    // Include fencing token in operation
    op.FencingToken = token
    return op.Execute(ctx)
}

// Storage verifies token
func (s *Storage) Write(ctx context.Context, op WriteOperation) error {
    currentToken := s.getCurrentLeaseToken(op.Resource)
    if op.FencingToken < currentToken {
        return ErrStaleLeaseHolder
    }
    return s.backend.Write(op.Key, op.Value)
}
```

---

## Systemic Prevention

### Monitoring

```promql
# Lease lost (acquired by someone else)
- alert: LeaseLost
  expr: |
    rate(lease_renewal_rejected_total[5m]) > 0.1
  labels:
    severity: warning

# Fencing token mismatch
- alert: FencingTokenMismatch
  expr: |
    rate(stale_fencing_token_total[5m]) > 0.01
  labels:
    severity: critical

# Clock skew detected
- alert: ClockSkew
  expr: |
    abs(time() - node_time_seconds) > 1
  labels:
    severity: warning
```

---

**Next Problem:** `advanced/postgres-103-schema-migration/`
