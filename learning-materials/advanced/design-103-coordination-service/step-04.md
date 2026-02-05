# Step 04: Distributed Locks with Auto-Expiry

---

## The Problem

You need to prevent multiple services from processing the same resource.

```
❌ Without distributed lock:

Worker 1: "I'm processing order-123"
Worker 2: "I'm also processing order-123"

Result:
- Order processed twice
- Inventory reserved twice
- Customer charged twice
- DATA CORRUPTION
```

---

## The Challenge: Lock Holder Crash

What happens if the service holding the lock crashes?

```
┌─────────────────────────────────────────────────────────────┐
│  Scenario: Lock Holder Crash                                 │
│                                                             │
│  Worker 1 acquires lock for order-123                       │
│  └─▶ Starts processing                                      │
│  └─▶ 💥 CRASH! (before releasing lock)                      │
│                                                             │
│  Worker 2 tries to acquire lock:                             │
│  └─▶ Lock still held (by dead Worker 1)                      │
│  └─▶ Wait... wait... wait...                                 │
│  └─▶ ❌ DEADLOCK (order never processed)                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Solution: Leases with TTL

The lock **auto-expires** after a timeout if not renewed.

```
┌─────────────────────────────────────────────────────────────┐
│  Distributed Lock with TTL (30 seconds):                     │
│                                                             │
│  Worker 1 acquires lock for order-123                       │
│     └─▶ Sets key: /locks/order-123 = "worker-1"            │
│         TTL: 30 seconds                                     │
│                                                             │
│  Every 10 seconds:                                          │
│     └─▶ Worker 1 refreshes: extends TTL to 30s            │
│                                                             │
│  If Worker 1 crashes:                                      │
│     └─▶ TTL not renewed                                    │
│     └─▶ After 30s, key expires                             │
│     └─▶ Worker 2 can acquire lock                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation in Go

```go
package coordination

import (
    "context"
    "time"

    clientv3 "go.etcd.io/etcd/client/v3"
    "go.etcd.io/etcd/client/v3/concurrency"
)

type DistributedLock struct {
    client  *clientv3.Client
    lockKey string
    mutex   *concurrency.Mutex
    session *concurrency.Session
    ttl     time.Duration
}

func NewDistributedLock(etcdEndpoints []string, lockKey string, ttl time.Duration) (*DistributedLock, error) {
    cli, err := clientv3.New(clientv3.Config{
        Endpoints:   etcdEndpoints,
        DialTimeout: 5 * time.Second,
    })
    if err != nil {
        return nil, err
    }

    return &DistributedLock{
        client:  cli,
        lockKey: "/locks/" + lockKey,
        ttl:     ttl,
    }, nil
}

func (dl *DistributedLock) Acquire(ctx context.Context) error {
    // Create session with TTL (auto-expires)
    session, err := concurrency.NewSession(ctx, dl.client,
        concurrency.WithTTL(int(dl.ttl.Seconds())))
    if err != nil {
        return err
    }
    dl.session = session

    // Create mutex
    dl.mutex = concurrency.NewMutex(session, dl.lockKey)

    // Try to acquire lock
    return dl.mutex.Lock(ctx)
}

func (dl *DistributedLock) Release(ctx context.Context) error {
    if dl.mutex != nil {
        if err := dl.mutex.Unlock(ctx); err != nil {
            return err
        }
    }
    if dl.session != nil {
        dl.session.Close()
    }
    return nil
}

// Usage
func ExampleLockUsage() {
    ctx := context.Background()

    lock, _ := NewDistributedLock([]string{"localhost:2379"}, "order-123", 30*time.Second)

    if err := lock.Acquire(ctx); err == nil {
        defer lock.Release(ctx)

        // Do work while periodically refreshing
        ticker := time.NewTicker(10 * time.Second)
        defer ticker.Stop()

        workDone := make(chan error)
        go func() {
            // Do work here
            workDone <- processOrder(ctx, "order-123")
        }()

        for {
            select {
            case err := <-workDone:
                return err
            case <-ticker.C:
                // Session auto-renews, but we can check if still valid
                if dl.session.Done() != nil {
                    // Session died, need to reacquire
                    return ErrLockLost
                }
            }
        }
    }
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What is the zombie leader problem? (Old leader thinks it's still leader after partition heals)
2. How does TTL solve this? (Leadership expires automatically)
3. How often should you refresh the TTL? (More frequently than the TTL value)
4. What's the difference between a lock and a lease? (Lock must be released, lease expires)

---

**Ready for high availability considerations? Read `step-05.md`**
