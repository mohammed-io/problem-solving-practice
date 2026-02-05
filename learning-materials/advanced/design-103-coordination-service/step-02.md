# Step 02: High Availability and Fencing

---

## Question 4: High Availability of Coordination Service

**etcd needs quorum (majority) to operate:**

```
3-node cluster:
- Quorum = 2 nodes
- Can tolerate 1 node failure
- If 2 nodes fail: CLUSTER UNAVAILABLE

5-node cluster:
- Quorum = 3 nodes
- Can tolerate 2 node failures
- If 3 nodes fail: CLUSTER UNAVAILABLE
```

**Deployment:**

```yaml
# Spread across availability zones
etcd-1: zone-a
etcd-2: zone-b
etcd-3: zone-c

# If zone-a fails, 2 nodes remain → quorum maintained
```

---

## Handling etcd Unavailability

**What if etcd loses quorum?**

```go
package coordination

import (
    "context"
    "encoding/json"
    "os"
    "sync"
    "time"

    clientv3 "go.etcd.io/etcd/client/v3"
)

type CachedConfig struct {
    client    *clientv3.Client
    cache     map[string]string
    cacheFile string
    mu        sync.RWMutex
}

func NewCachedConfig(etcdEndpoints []string, cacheFile string) (*CachedConfig, error) {
    client, err := clientv3.New(clientv3.Config{
        Endpoints:   etcdEndpoints,
        DialTimeout: 5 * time.Second,
    })
    if err != nil {
        return nil, err
    }

    cc := &CachedConfig{
        client:    client,
        cache:     make(map[string]string),
        cacheFile: cacheFile,
    }

    // Load cache from disk
    cc.loadCache()

    return cc, nil
}

func (cc *CachedConfig) Get(ctx context.Context, key string) (string, bool) {
    // Try cache first
    cc.mu.RLock()
    if value, ok := cc.cache[key]; ok {
        cc.mu.RUnlock()
        return value, true
    }
    cc.mu.RUnlock()

    // Try etcd
    resp, err := cc.client.Get(ctx, "/config/"+key)
    if err != nil {
        // etcd unavailable, return cached value if exists
        cc.mu.RLock()
        defer cc.mu.RUnlock()
        if value, ok := cc.cache[key]; ok {
            return value, true // Return stale but cached
        }
        return "", false
    }

    if len(resp.Kvs) > 0 {
        value := string(resp.Kvs[0].Value)

        // Update cache
        cc.mu.Lock()
        cc.cache[key] = value
        cc.mu.Unlock()

        // Persist cache
        cc.saveCache()

        return value, true
    }

    return "", false
}

func (cc *CachedConfig) Watch(ctx context.Context, key string, callback func(string)) {
    watchChan := cc.client.Watch(ctx, "/config/"+key)

    for {
        select {
        case <-ctx.Done():
            return
        case resp := <-watchChan:
            for _, event := range resp.Events {
                if event.Type == clientv3.EventTypePut {
                    value := string(event.Kv.Value)

                    // Update cache
                    cc.mu.Lock()
                    cc.cache[key] = value
                    cc.mu.Unlock()

                    // Call callback
                    callback(value)
                }
            }
        }
    }
}

func (cc *CachedConfig) loadCache() {
    data, err := os.ReadFile(cc.cacheFile)
    if err != nil {
        return
    }

    cc.mu.Lock()
    defer cc.mu.Unlock()

    json.Unmarshal(data, &cc.cache)
}

func (cc *CachedConfig) saveCache() {
    cc.mu.RLock()
    data, err := json.Marshal(cc.cache)
    cc.mu.RUnlock()

    if err != nil {
        return
    }

    _ = os.WriteFile(cc.cacheFile, data, 0644)
}
```

**Strategy:** Services cache config locally. If etcd is down, they use stale config but continue operating.

---

## Fencing Tokens (Prevent Split Brain)

**The zombie leader problem:**

```
1. Service A is leader
2. Network partition isolates Service A
3. Service B becomes new leader
4. Partition heals
5. Service A still thinks it's leader! (zombie)
6. Both write to database → DATA CORRUPTION
```

**Solution: Fencing tokens**

```go
package coordination

import (
    "context"
    "time"

    clientv3 "go.etcd.io/etcd/client/v3"
    "github.com/google/uuid"
)

type FencedLeader struct {
    etcd         *clientv3.Client
    fencingToken string
    electionPath string
}

func NewFencedLeader(etcdEndpoints []string, electionPath string) (*FencedLeader, error) {
    client, err := clientv3.New(clientv3.Config{
        Endpoints:   etcdEndpoints,
        DialTimeout: 5 * time.Second,
    })
    if err != nil {
        return nil, err
    }

    return &FencedLeader{
        etcd:         client,
        electionPath: electionPath,
    }, nil
}

func (fl *FencedLeader) BecomeLeader(ctx context.Context) error {
    // Generate fencing token
    fl.fencingToken = uuid.New().String()

    // Store in etcd (overwrites any existing)
    _, err := fl.etcd.Put(ctx, "/leader/fencing-token", fl.fencingToken)
    if err != nil {
        return err
    }

    return nil
}

func (fl *FencedLeader) IsWriteValid(ctx context.Context, token string) (bool, error) {
    // Check if our fencing token is still valid
    resp, err := fl.etcd.Get(ctx, "/leader/fencing-token")
    if err != nil {
        return false, err
    }

    if len(resp.Kvs) == 0 {
        return false, nil
    }

    currentToken := string(resp.Kvs[0].Value)
    return currentToken == token, nil
}

func (fl *FencedLeader) GetFencingToken() string {
    return fl.fencingToken
}

// Database side would verify the token
type WriteRequest struct {
    ID    string
    Token string // Fencing token
    Data  interface{}
}

func (db *Database) WriteWithFencing(ctx context.Context, req WriteRequest) error {
    // Check if token is valid
    valid, err := db.ValidateFencingToken(ctx, req.Token)
    if err != nil {
        return err
    }
    if !valid {
        return ErrInvalidFencingToken
    }

    // Proceed with write
    return db.write(ctx, req.Data)
}
```

**Database side:**

```sql
-- Table to track fencing tokens
CREATE TABLE fencing_tokens (
    service VARCHAR(50),
    token UUID NOT NULL,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '1 minute',
    PRIMARY KEY (service, valid_until)
);

-- Before write, check if token is valid
-- If token's valid_until < NOW(), reject write
```

---

## Monitoring Coordination Service

```go
package monitoring

import (
    "context"
    "time"

    clientv3 "go.etcd.io/etcd/client/v3"
    "github.com/prometheus/client_golang/prometheus"
)

type EtcdMonitor struct {
    client       *clientv3.Client
    clusterSize  prometheus.Gauge
    isLeader     prometheus.Gauge
    endpointHealth map[string]prometheus.Gauge
}

func NewEtcdMonitor(etcdEndpoints []string) (*EtcdMonitor, error) {
    client, err := clientv3.New(clientv3.Config{
        Endpoints:   etcdEndpoints,
        DialTimeout: 5 * time.Second,
    })
    if err != nil {
        return nil, err
    }

    em := &EtcdMonitor{
        client:       client,
        endpointHealth: make(map[string]prometheus.Gauge),
    }

    // Initialize metrics
    em.clusterSize = prometheus.NewGauge(prometheus.GaugeOpts{
        Name: "etcd_cluster_size",
        Help: "Size of the etcd cluster",
    })

    em.isLeader = prometheus.NewGauge(prometheus.GaugeOpts{
        Name: "etcd_is_leader",
        Help: "1 if this instance is leader, 0 otherwise",
    })

    // Initialize endpoint health gauges
    for _, endpoint := range etcdEndpoints {
        em.endpointHealth[endpoint] = prometheus.NewGauge(prometheus.GaugeOpts{
            Name:        "etcd_endpoint_health",
            Help:        "Health of etcd endpoint (1=healthy, 0=unhealthy)",
            ConstLabels: prometheus.Labels{"endpoint": endpoint},
        })
    }

    return em, nil
}

func (em *EtcdMonitor) Run(ctx context.Context) {
    ticker := time.NewTicker(10 * time.Second)
    defer ticker.Stop()

    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            em.checkClusterHealth(ctx)
        }
    }
}

func (em *EtcdMonitor) checkClusterHealth(ctx context.Context) {
    // Check cluster health
    resp, err := em.client.MemberList(ctx)
    if err != nil {
        return
    }

    em.clusterSize.Set(float64(len(resp.Members)))

    // Check if leader
    statusResp, err := em.client.Status(ctx, em.client.Endpoints()[0])
    if err == nil {
        if statusResp.Leader == statusResp.Header.MemberId {
            em.isLeader.Set(1)
        } else {
            em.isLeader.Set(0)
        }
    }

    // Check endpoint health
    for _, endpoint := range em.client.Endpoints() {
        _, err := em.client.Status(ctx, endpoint)
        if err != nil {
            em.endpointHealth[endpoint].Set(0)
        } else {
            em.endpointHealth[endpoint].Set(1)
        }
    }
}
```

---

## Summary

| Concern | Solution |
|---------|----------|
| **HA deployment** | 3 or 5 nodes across AZs |
| **Quorum loss** | Cache config locally, operate in degraded mode |
| **Zombie leaders** | Fencing tokens validated by database |
| **Connection failures** | Retry with exponential backoff |
| **Monitoring** | Track cluster health, endpoint status |

---

**Now read `solution.md` for complete implementation.**
