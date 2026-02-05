# Step 2: Solutions for Thundering Herd

---

## Solution 1: Request Coalescing (Singleflight)

```go
import "golang.org/x/sync/singleflight"

var sf singleflight.Group

func GetUserProfile(ctx context.Context, userID int64) (*Profile, error) {
    key := strconv.FormatInt(userID, 10)

    // Try cache first
    if cached, err := redis.Get("user:" + key); err == nil {
        return unserialize(cached), nil
    }

    // Singleflight: only one goroutine per key fetches from DB
    result, err, shared := sf.Do(key, func() (interface{}, error) {
        profile, err := db.QueryRow("SELECT * FROM users WHERE id = $1", userID)
        if err != nil {
            return nil, err
        }

        // Populate cache
        redis.Set("user:"+key, serialize(profile), 1*time.Hour)
        return profile, nil
    })

    if shared {
        metrics.CoalescedRequests.Inc()
    }

    return result.(*Profile), err
}
```

**Result:** If 1000 requests simultaneously miss cache for user 123, only 1 DB query happens.

---

## Solution 2: Probabilistic Cache Refresh

```go
func GetUserProfile(userID int64) (*Profile, error) {
    key := "user:" + strconv.FormatInt(userID, 10)

    cached, err := redis.Get(key)
    if err == nil {
        // 5% chance to refresh proactively
        if rand.Float64() < 0.05 {
            go refreshInBackground(userID, key)
        }
        return unserialize(cached), nil
    }

    // Cache miss: fetch from DB
    profile, err := db.QueryRow("SELECT * FROM users WHERE id = $1", userID)
    redis.Set(key, serialize(profile), 1*time.Hour)
    return profile, nil
}
```

Hot keys refresh before expiring. Cold cache = gradual warmup, not sudden.

---

## Quick Check

Before moving on, make sure you understand:

1. What is singleflight? (Coalesce concurrent requests for same key into one)
2. How does singleflight reduce load? (1000 requests → 1 database query)
3. What's probabilistic cache refresh? (Random chance to refresh before expiry)
4. Why refresh before expiry? (Prevents simultaneous expiry stampede)
5. How do these solutions help during restart? (Gradual warmup, not sudden spike)

---

**Continue to `solution.md`**
