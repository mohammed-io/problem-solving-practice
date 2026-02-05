# Step 06: Handling Coordination Service Failures

---

## The Problem

Even with a 3-node cluster, etcd can lose quorum.

```
┌─────────┐  ┌─────────┐  ┌─────────┐
│ etcd-1  │  │ etcd-2  │  │ etcd-3  │
└────┬────┘  └────┬────┘  └────┬────┘
     │            │            │
   AZ-1a        AZ-1b        AZ-1c
     │            │            │
     └────────────┴────────────┘
                  │
             ⚡ Network partition
             │ isolates AZ-1a, AZ-1b

┌─────────┐  ┌─────────┐
│ etcd-1  │  │ etcd-2  │  ← ISOLATED (can't reach etcd-3)
└─────────┘  └─────────┘

Result: 2 nodes remain, but they can't reach each other
→ Quorum lost
→ CLUSTER UNAVAILABLE
```

---

## Strategy 1: Local Config Cache

Services cache etcd data locally. If etcd is down, use stale config.

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

    // Load cache from disk on startup
    cc.loadCache()

    return cc, nil
}

func (cc *CachedConfig) Get(ctx context.Context, key string) (string, bool) {
    // Try cache first (fast path)
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

        // Persist cache to disk
        cc.saveCache()

        return value, true
    }

    return "", false
}

func (cc *CachedConfig) loadCache() {
    data, _ := os.ReadFile(cc.cacheFile)
    json.Unmarshal(data, &cc.cache)
}

func (cc *CachedConfig) saveCache() {
    cc.mu.RLock()
    data, _ := json.Marshal(cc.cache)
    cc.mu.RUnlock()
    os.WriteFile(cc.cacheFile, data, 0644)
}
```

---

## Strategy 2: Graceful Degradation

Define behavior for each coordination primitive when etcd is unavailable:

| Primitive | With etcd | Without etcd |
|-----------|-----------|---------------|
| **Leader election** | Automatic | No new elections (existing leaders stay) |
| **Distributed lock** | Acquire with TTL | Use local locks with risk of conflict |
| **Configuration** | Real-time updates | Use cached config (possibly stale) |
| **Service discovery** | Real-time endpoints | Use cached endpoint list |

```go
type EtcdAvailability int

const (
    EtcdAvailable EtcdAvailability = iota
    EtcdDegraded
    EtcdUnavailable
)

func (s *Service) checkEtcdHealth(ctx context.Context) EtcdAvailability {
    ctx, cancel := context.WithTimeout(ctx, 1*time.Second)
    defer cancel()

    _, err := s.etcd.Client.Get(ctx, "health")
    if err != nil {
        return EtcdUnavailable
    }
    return EtcdAvailable
}

func (s *Service) GetConfig(ctx context.Context, key string) (string, error) {
    switch s.checkEtcdHealth(ctx) {
    case EtcdAvailable:
        return s.etcd.Get(ctx, key)  // Real-time
    case EtcdDegraded, EtcdUnavailable:
        return s.cache.Get(ctx, key)  // Stale but better than nothing
    }
}
```

---

## Strategy 3: Retry with Exponential Backoff

When etcd is temporarily unavailable, retry with increasing delays:

```go
func (s *Service) GetWithRetry(ctx context.Context, key string) (string, error) {
    maxAttempts := 3
    baseDelay := 100 * time.Millisecond

    for attempt := 0; attempt < maxAttempts; attempt++ {
        value, err := s.etcd.Get(ctx, key)
        if err == nil {
            return value, nil
        }

        // Check if error is retryable
        if attempt == maxAttempts-1 {
            return "", err
        }

        // Exponential backoff: 100ms, 200ms, 400ms
        delay := baseDelay * time.Duration(1<<attempt)
        select {
        case <-time.After(delay):
            continue
        case <-ctx.Done():
            return "", ctx.Err()
        }
    }

    return "", ErrEtcdUnavailable
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What causes quorum loss? (Network partition, node failures)
2. How does local caching help? (Services function with stale config)
3. What is graceful degradation? (Different behavior based on availability)
4. How does retry help? (Handle transient failures)

---

**Ready to prevent split-brain? Read `step-07.md`**
