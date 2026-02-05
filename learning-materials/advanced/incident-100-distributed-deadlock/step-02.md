# Step 2: Distributed Lock Safety and Idempotency

---

## Safe Distributed Locks

The original Lock function has a bug:

```go
// BAD: Lock can be set without expiry if Redis crashes mid-command
func Lock(key string) bool {
    result, _ := redis.SetNX(ctx, "lock:"+key, "locked", 30*time.Second).Result()
    return result
}
```

**Better: Use Lua script for atomicity**

```go
// GOOD: Lock is atomic with expiry
func Lock(key string, expiry time.Duration) (bool, error) {
    // Lua script runs atomically on Redis
    script := `
        if redis.call("exists", KEYS[1]) == 0 then
            return redis.call("setex", KEYS[1], ARGV[1], ARGV[2])
        else
            return 0
        end
    `
    result, err := redis.Eval(ctx, script, []string{"lock:" + key},
        int(expiry.Seconds()), uuid.New().String()).Result()
    return result.(int64) == 1, err
}

// GOOD: Only unlock if you own the lock
func Unlock(key string, token string) error {
    script := `
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
    `
    _, err := redis.Eval(ctx, script, []string{"lock:" + key}, token).Result()
    return err
}
```

**Key improvements:**
1. Token-based unlocking (can't unlock someone else's lock)
2. Set with expiry in one atomic operation
3. Safe against Redis crashes

---

## Idempotent Transfers

To prevent duplicates, store transfer intent before acting:

```go
func Transfer(idempotencyKey, fromAccount, toAccount string, amount float64) error {
    // Check if already processed
    if alreadyProcessed(idempotencyKey) {
        return nil  // Idempotent!
    }

    // Record intent (durable storage, not memory)
    if err := recordIntent(idempotencyKey, fromAccount, toAccount, amount); err != nil {
        return err
    }

    // Now proceed with transfer with locks
    ...

    // Mark complete
    markProcessed(idempotencyKey)
    return nil
}
```

**Storage for intent:** Must be durable (database, not memory).

---

## Quick Check

Before moving on, make sure you understand:

1. What's wrong with basic SetNX for locking? (Can set without expiry if Redis crashes)
2. How does Lua script improve lock safety? (Atomic set+expire, token-based unlock)
3. What is idempotency? (Same operation twice = same result as once)
4. How do idempotency keys prevent duplicate transfers? (Check if processed before executing)
5. Why must intent storage be durable? (Memory lost on crash, duplicate retries happen)

---

**Continue to `solution.md`**
