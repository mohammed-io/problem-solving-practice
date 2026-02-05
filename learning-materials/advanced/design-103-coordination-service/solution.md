---
name: design-103-coordination-service
description: Coordination services for distributed systems - leader election, configuration management, distributed locking
difficulty: Advanced
category: Distributed Systems
level: Principal Engineer
---

# Solution: Coordination Service

---

## Answers

### 1. Which Coordination Service?

**Recommendation: etcd**

| Reason | Explanation |
|--------|-------------|
| **Simplicity** | Simple API, easy to understand |
| **Performance** | Fast (Raft is efficient) |
| **Ecosystem** | Used by Kubernetes, battle-tested |
| **Multi-language** | gRPC supports all languages |
| **Strong consistency** | Linearizable reads and writes |

**ZooKeeper** if you need:
- Complex ACLs
- Java-centric ecosystem
- Specific ZK features (recipes)

**Consul** if you need:
- Built-in DNS interface
- Health checking
- Service discovery out of the box

### 2. Leader Election with Crash Recovery

```go
package coordination

import (
    "context"
    "fmt"
    "time"

    clientv3 "go.etcd.io/etcd/client/v3"
    "go.etcd.io/etcd/client/v3/concurrency"
)

type LeaderElection struct {
    client       *clientv3.Client
    electionPath string
    session      *concurrency.Session
    election     *concurrency.Election
    leader       bool
}

func NewLeaderElection(etcdEndpoints []string, electionPath string) (*LeaderElection, error) {
    cli, err := clientv3.New(clientv3.Config{
        Endpoints:   etcdEndpoints,
        DialTimeout: 5 * time.Second,
    })
    if err != nil {
        return nil, err
    }

    return &LeaderElection{
        client:       cli,
        electionPath: electionPath,
    }, nil
}

func (le *LeaderElection) Campaign(ctx context.Context) error {
    for {
        select {
        case <-ctx.Done():
            return ctx.Err()
        default:
        }

        // Create session with TTL
        session, err := concurrency.NewSession(ctx, le.client,
            concurrency.WithTTL(10)) // Leadership expires in 10s
        if err != nil {
            time.Sleep(time.Second)
            continue
        }
        le.session = session

        // Create election
        election := concurrency.NewElection(session, le.electionPath)
        le.election = election

        // Campaign for leadership
        if err := election.Campaign(ctx, "my-instance-id"); err != nil {
            time.Sleep(time.Second)
            continue
        }

        // I'm leader!
        le.leader = true
        le.onElected()

        // Monitor leadership
        le.monitorLeadership(ctx)
    }
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
                le.onRemoved()
                return
            }
        }
    }
}

func (le *LeaderElection) onElected() {
    fmt.Println("Became leader, starting work...")
    // Start leader work in background
}

func (le *LeaderElection) onRemoved() {
    fmt.Println("Lost leadership, stopping work...")
    // Stop leader work
}
```

**Crash recovery:** The TTL ensures leadership expires if leader crashes. Other candidates can then acquire leadership.

### 3. Distributed Lock with Crash Safety

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
}

func NewDistributedLock(etcdEndpoints []string, lockKey string) (*DistributedLock, error) {
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
    }, nil
}

func (dl *DistributedLock) Acquire(ctx context.Context) error {
    // Create session with TTL (auto-expires)
    session, err := concurrency.NewSession(ctx, dl.client,
        concurrency.WithTTL(30)) // Auto-expires in 30s
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

    lock, _ := NewDistributedLock([]string{"localhost:2379"}, "order-123")

    if err := lock.Acquire(ctx); err == nil {
        defer lock.Release(ctx)

        // Do work while renewing lock
        ticker := time.NewTicker(10 * time.Second)
        defer ticker.Stop()

        workDone := make(chan bool)
        go func() {
            // Do work here
            workDone <- true
        }()

        for {
            select {
            case <-workDone:
                return
            case <-ticker.C:
                // Session auto-renews, just check if still valid
            }
        }
    }
}
```

**Crash safety:** If lock holder crashes without releasing, TTL expires automatically after 30 seconds.

### 4. High Availability of Coordination Service

```yaml
# etcd cluster: 3 or 5 nodes (odd number for quorum)
etcd-1: 10.0.0.1
etcd-2: 10.0.0.2
etcd-3: 10.0.0.3

# Quorum = 2 (majority of 3)
# - Can tolerate 1 node failure
# - Writes require 2 nodes to acknowledge
# - Reads require quorum for consistency
```

**Multi-region strategy:**
- Single etcd cluster in primary region
- Read-only replicas in other regions (eventual consistency)
- Or: Federated clusters per region with cross-region sync

### 5. Coordination Layer Design

```go
package coordination

import (
    "context"
    "encoding/json"

    clientv3 "go.etcd.io/etcd/client/v3"
)

type CoordinationLayer struct {
    etcd *clientv3.Client
}

func NewCoordinationLayer(etcdEndpoints []string) (*CoordinationLayer, error) {
    cli, err := clientv3.New(clientv3.Config{
        Endpoints:   etcdEndpoints,
        DialTimeout: 5 * time.Second,
    })
    if err != nil {
        return nil, err
    }

    return &CoordinationLayer{etcd: cli}, nil
}

// Leader election
func (cl *CoordinationLayer) ElectLeader(ctx context.Context, service string) (*LeaderElection, error) {
    return NewLeaderElection(cl.etcd.Endpoints(), "/election/"+service)
}

// Distributed lock
func (cl *CoordinationLayer) AcquireLock(ctx context.Context, resource string) (*DistributedLock, error) {
    return NewDistributedLock(cl.etcd.Endpoints(), resource)
}

// Configuration
func (cl *CoordinationLayer) GetConfig(ctx context.Context, key string) (string, error) {
    resp, err := cl.etcd.Get(ctx, "/config/"+key)
    if err != nil {
        return "", err
    }

    if len(resp.Kvs) == 0 {
        return "", nil
    }

    return string(resp.Kvs[0].Value), nil
}

func (cl *CoordinationLayer) WatchConfig(ctx context.Context, key string) (<-chan string, error) {
    ch := make(chan string)

    watchChan := cl.etcd.Watch(ctx, "/config/"+key)
    go func() {
        defer close(ch)
        for {
            select {
            case <-ctx.Done():
                return
            case resp := <-watchChan:
                for _, event := range resp.Events {
                    if event.Type == clientv3.EventTypePut {
                        ch <- string(event.Kv.Value)
                    }
                }
            }
        }
    }()

    return ch, nil
}

// Service discovery
type ServiceInstance struct {
    Address string `json:"address"`
    Port    int    `json:"port"`
}

func (cl *CoordinationLayer) RegisterService(ctx context.Context, serviceName, instanceID string, address string, port int) error {
    key := "/services/" + serviceName + "/" + instanceID

    instance := ServiceInstance{
        Address: address,
        Port:    port,
    }

    data, err := json.Marshal(instance)
    if err != nil {
        return err
    }

    // Create lease with TTL (ephemeral node)
    lease, err := cl.etcd.Grant(ctx, 10) // 10 second TTL
    if err != nil {
        return err
    }

    // Put with lease
    _, err = cl.etcd.Put(ctx, key, string(data), clientv3.WithLease(lease.ID))
    return err
}

func (cl *CoordinationLayer) DiscoverServices(ctx context.Context, serviceName string) ([]ServiceInstance, error) {
    prefix := "/services/" + serviceName + "/"

    resp, err := cl.etcd.Get(ctx, prefix, clientv3.WithPrefix())
    if err != nil {
        return nil, err
    }

    var instances []ServiceInstance
    for _, kv := range resp.Kvs {
        var instance ServiceInstance
        if err := json.Unmarshal(kv.Value, &instance); err == nil {
            instances = append(instances, instance)
        }
    }

    return instances, nil
}
```

---

## Best Practices

### 1. Fencing Tokens

Prevent "zombie" leaders from making changes:

```go
package fencing

import (
    "context"
    "time"

    clientv3 "go.etcd.io/etcd/client/v3"
    "github.com/google/uuid"
)

type FencingTokenManager struct {
    etcd *clientv3.Client
}

func NewFencingTokenManager(etcdEndpoints []string) (*FencingTokenManager, error) {
    cli, err := clientv3.New(clientv3.Config{
        Endpoints:   etcdEndpoints,
        DialTimeout: 5 * time.Second,
    })
    if err != nil {
        return nil, err
    }

    return &FencingTokenManager{etcd: cli}, nil
}

func (ftm *FencingTokenManager) GenerateToken(ctx context.Context, service string) (string, error) {
    // Generate fencing token
    token := uuid.New().String()

    // Store in etcd (overwrites any existing)
    key := "/leader/" + service + "/fencing-token"
    _, err := ftm.etcd.Put(ctx, key, token)
    if err != nil {
        return "", err
    }

    return token, nil
}

func (ftm *FencingTokenManager) ValidateToken(ctx context.Context, service, token string) (bool, error) {
    key := "/leader/" + service + "/fencing-token"
    resp, err := ftm.etcd.Get(ctx, key)
    if err != nil {
        return false, err
    }

    if len(resp.Kvs) == 0 {
        return false, nil
    }

    currentToken := string(resp.Kvs[0].Value)
    return currentToken == token, nil
}

// Usage in database writes
type WriteWithToken struct {
    ID    string
    Token string
    Data  interface{}
}

func (db *Database) Write(ctx context.Context, req WriteWithToken) error {
    // Validate fencing token
    valid, _ := db.fencing.ValidateToken(ctx, "order-service", req.Token)
    if !valid {
        return ErrInvalidToken
    }

    // Include fencing token in all writes
    return db.write(ctx, req.Data, req.Token)
}
```

### 2. Connection Handling

```go
package coordination

import (
    "context"
    "time"

    clientv3 "go.etcd.io/etcd/client/v3"
)

type ResilientEtcd struct {
    endpoints []string
    client    *clientv3.Client
    mu        chan struct{}
}

func NewResilientEtcd(endpoints []string) *ResilientEtcd {
    re := &ResilientEtcd{
        endpoints: endpoints,
        mu:        make(chan struct{}, 1),
    }
    re.connect()
    return re
}

func (re *ResilientEtcd) connect() error {
    for {
        cli, err := clientv3.New(clientv3.Config{
            Endpoints:   re.endpoints,
            DialTimeout: 5 * time.Second,
        })
        if err != nil {
            time.Sleep(time.Second)
            continue
        }

        // Test connection
        ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
        _, err = cli.Get(ctx, "health")
        cancel()

        if err != nil {
            time.Sleep(time.Second)
            continue
        }

        re.client = cli
        return nil
    }
}

func (re *ResilientEtcd) Get(ctx context.Context, key string, opts ...clientv3.OpOption) (*clientv3.GetResponse, error) {
    resp, err := re.client.Get(ctx, key, opts...)
    if err != nil {
        // Retry connection
        _ = re.connect()
        return re.client.Get(ctx, key, opts...)
    }
    return resp, nil
}

func (re *ResilientEtcd) Put(ctx context.Context, key, val string, opts ...clientv3.OpOption) (*clientv3.PutResponse, error) {
    resp, err := re.client.Put(ctx, key, val, opts...)
    if err != nil {
        _ = re.connect()
        return re.client.Put(ctx, key, val, opts...)
    }
    return resp, nil
}
```

### 3. Cache Coordination Data

```go
package cache

import (
    "sync"
    "time"
)

type LeaderCache struct {
    cachedLeader string
    cachedAt     time.Time
    cacheTTL     time.Duration
    mu           sync.RWMutex
}

func NewLeaderCache(cacheTTL time.Duration) *LeaderCache {
    return &LeaderCache{
        cacheTTL: cacheTTL,
    }
}

func (lc *LeaderCache) IsLeader(fn func() (string, error)) (bool, error) {
    lc.mu.RLock()
    now := time.Now()
    if lc.cachedLeader != "" && now.Sub(lc.cachedAt) < lc.cacheTTL {
        leader := lc.cachedLeader
        lc.mu.RUnlock()
        return leader == "my-instance-id", nil
    }
    lc.mu.RUnlock()

    // Cache expired, fetch fresh
    leader, err := fn()
    if err != nil {
        return false, err
    }

    lc.mu.Lock()
    lc.cachedLeader = leader
    lc.cachedAt = now
    lc.mu.Unlock()

    return leader == "my-instance-id", nil
}
```

---

## Summary

| Component | Implementation | Notes |
|-----------|----------------|-------|
| **Leader election** | etcd election API | Auto-renew, handle removal |
| **Distributed lock** | etcd lease with TTL | Auto-expiry on crash |
| **Config storage** | etcd key-value | Watch for changes |
| **Service discovery** | Ephemeral nodes + prefix query | TTL=session |
| **HA deployment** | 3 or 5 node cluster | Quorum = majority |
| **Fencing** | UUID tokens stored in etcd | Prevents split-brain writes |
