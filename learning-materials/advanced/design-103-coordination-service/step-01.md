# Step 01: Coordination Service Basics

---

## Question 1: Which Coordination Service?

**Answer: etcd** (in most cases)

**Why etcd?**

| Factor | etcd | ZooKeeper | Consul |
|--------|------|-----------|--------|
| Simplicity | ✅ Simple API | ❌ Complex | ✅ Medium |
| Performance | ✅ Fast (~10ms) | ❌ Slower (~50ms) | ✅ Fast (~20ms) |
| Multi-region | ✅ Supported | ❌ No native support | ✅ Supported |
| Ecosystem | ✅ K8s default | ✅ Hadoop ecosystem | ✅ Service discovery |
| Language | ✅ All (gRPC) | ⚠️ Java-first | ✅ All (HTTP) |

**Use ZooKeeper if:** You're in the Hadoop ecosystem, need complex ACLs
**Use Consul if:** You want built-in DNS, health checking, service discovery

---

## Question 2: Leader Election with Crash Recovery

**The problem:** Leader crashes, followers need to know and elect new leader.

**Solution: TTL-based elections**

```go
package coordination

import (
    "context"
    "time"

    clientv3 "go.etcd.io/etcd/client/v3"
    "go.etcd.io/etcd/client/v3/concurrency"
)

type LeaderElection struct {
    client     *clientv3.Client
    electionPath string
    session    *concurrency.Session
    election   *concurrency.Election
    leader     bool
    onElected  func()
    onRemoved  func()
}

func NewLeaderElection(etcdEndpoints []string, electionPath string, onElected, onRemoved func()) (*LeaderElection, error) {
    cli, err := clientv3.New(clientv3.Config{
        Endpoints:   etcdEndpoints,
        DialTimeout: 5 * time.Second,
    })
    if err != nil {
        return nil, err
    }

    return &LeaderElection{
        client:      cli,
        electionPath: electionPath,
        onElected:   onElected,
        onRemoved:   onRemoved,
    }, nil
}

func (le *LeaderElection) Campaign(ctx context.Context) error {
    // Create a session with TTL
    session, err := concurrency.NewSession(ctx, le.client,
        concurrency.WithTTL(10)) // Leadership expires in 10s
    if err != nil {
        return err
    }
    le.session = session

    // Create election
    election := concurrency.NewElection(session, le.electionPath)
    le.election = election

    // Campaign for leadership
    if err := election.Campaign(ctx, "my-instance-id"); err != nil {
        return err
    }

    // I'm leader!
    le.leader = true
    if le.onElected != nil {
        le.onElected()
    }

    // Wait for leadership to be lost
    go le.monitorLeadership(ctx)

    return nil
}

func (le *LeaderElection) monitorLeadership(ctx context.Context) {
    ch := le.election.Observe(ctx)

    for {
        select {
        case <-ctx.Done():
            return
        case resp := <-ch:
            // If we're no longer the leader
            if resp == nil || resp.Kvs == nil {
                le.leader = false
                if le.onRemoved != nil {
                    le.onRemoved()
                }
                return
            }
        }
    }
}

func (le *LeaderElection) Resign(ctx context.Context) error {
    if le.election != nil {
        return le.election.Resign(ctx)
    }
    return nil
}

func (le *LeaderElection) Close() error {
    if le.session != nil {
        le.session.Close()
    }
    return le.client.Close()
}
```

**On crash:**
- Leader crashes → stops renewing → TTL expires
- Other candidates notice → new election
- New leader emerges

---

## Question 3: Distributed Lock with Crash Safety

**The problem:** Lock holder crashes without releasing lock.

**Solution: Leases with auto-expiry**

```go
package coordination

import (
    "context"
    "time"

    clientv3 "go.etcd.io/etcd/client/v3"
    "go.etcd.io/etcd/client/v3/concurrency"
)

type DistributedLock struct {
    client    *clientv3.Client
    lockKey   string
    mutex     *concurrency.Mutex
    session   *concurrency.Session
    ttl       time.Duration
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

func (dl *DistributedLock) Refresh(ctx context.Context) error {
    // Session auto-renews, just check if still valid
    if dl.session == nil || dl.session.Done() != nil {
        return dl.Acquire(ctx)
    }
    return nil
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

func (dl *DistributedLock) Close() error {
    if dl.session != nil {
        dl.session.Close()
    }
    return dl.client.Close()
}

// Usage
func ExampleUsage() {
    ctx := context.Background()

    lock, err := NewDistributedLock([]string{"localhost:2379"}, "order-123", 30*time.Second)
    if err != nil {
        panic(err)
    }
    defer lock.Close()

    if err := lock.Acquire(ctx); err != nil {
        // Lock held by someone else
        panic(err)
    }

    // Do work while periodically refreshing
    done := make(chan bool)
    go func() {
        ticker := time.NewTicker(10 * time.Second)
        defer ticker.Stop()

        for {
            select {
            case <-done:
                return
            case <-ticker.C:
                _ = lock.Refresh(ctx)
            }
        }
    }()

    // Do work...

    // Explicitly release when done
    close(done)
    _ = lock.Release(ctx)
}
```

**If holder crashes:**
- Session isn't renewed
- TTL expires after 30s
- Lock becomes available
- Others can acquire

---

**Still thinking about high availability? Read `step-02.md`**
