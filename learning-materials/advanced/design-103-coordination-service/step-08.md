# Step 08: Service Discovery and Configuration

---

## Service Discovery

Services need to find each other dynamically.

```
❌ Hardcoded addresses:
   orderService := "http://order-service:8080"

   Problem:
   - What if order-service moves?
   - What if there are multiple instances?
   - How do you load balance?

✅ Service discovery:
   instances := discover("order-service")
   → ["http://order-service-1:8080", "http://order-service-2:8080"]
```

---

## Implementing Service Discovery

### Registration (Ephemeral Nodes)

```go
package coordination

import (
    "context"
    "encoding/json"
    "time"

    clientv3 "go.etcd.io/etcd/client/v3"
)

type ServiceInstance struct {
    ID        string    `json:"id"`
    Name      string    `json:"name"`
    Address   string    `json:"address"`
    Port      int       `json:"port"`
    Metadata  Metadata  `json:"metadata"`
    StartTime time.Time `json:"start_time"`
}

type Metadata struct {
    Version string `json:"version"`
    Region  string `json:"region"`
}

type ServiceRegistry struct {
    etcd     *clientv3.Client
}

func (sr *ServiceRegistry) Register(ctx context.Context, instance *ServiceInstance, ttl time.Duration) error {
    key := "/services/" + instance.Name + "/" + instance.ID

    data, err := json.Marshal(instance)
    if err != nil {
        return err
    }

    // Create lease with TTL
    lease, err := sr.etcd.Grant(ctx, int(ttl.Seconds()))
    if err != nil {
        return err
    }

    // Put with lease (ephemeral - dies when service stops)
    _, err = sr.etcd.Put(ctx, key, string(data), clientv3.WithLease(lease.ID))
    return err
}

// Service registers on startup
func (s *OrderService) Start(ctx context.Context) error {
    instance := &ServiceInstance{
        ID:        generateID(),
        Name:      "order-service",
        Address:   getLocalIP(),
        Port:      8080,
        Metadata:  Metadata{Version: "v2.3.1", Region: "us-east-1"},
        StartTime: time.Now(),
    }

    // Register with TTL (heartbeat)
    if err := s.registry.Register(ctx, instance, 10*time.Second); err != nil {
        return err
    }

    // Keep registration alive
    go s.heartbeat(ctx, instance)

    return nil
}

func (s *OrderService) heartbeat(ctx context.Context, instance *ServiceInstance) {
    ticker := time.NewTicker(5 * time.Second)
    defer ticker.Stop()

    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            s.registry.Register(ctx, instance, 10*time.Second)
        }
    }
}
```

### Discovery

```go
func (sr *ServiceRegistry) Discover(ctx context.Context, serviceName string) ([]*ServiceInstance, error) {
    prefix := "/services/" + serviceName + "/"

    resp, err := sr.etcd.Get(ctx, prefix, clientv3.WithPrefix())
    if err != nil {
        return nil, err
    }

    var instances []*ServiceInstance
    for _, kv := range resp.Kvs {
        var instance ServiceInstance
        if err := json.Unmarshal(kv.Value, &instance); err != nil {
            continue
        }
        instances = append(instances, &instance)
    }

    return instances, nil
}

// Client uses discovery
type OrderClient struct {
    registry *ServiceRegistry
}

func (c *OrderClient) GetOrder(ctx context.Context, orderID string) (*Order, error) {
    // Discover instances
    instances, err := c.registry.Discover(ctx, "order-service")
    if err != nil {
        return nil, err
    }

    if len(instances) == 0 {
        return nil, ErrNoInstancesAvailable
    }

    // Simple round-robin (in production, use proper load balancer)
    instance := instances[time.Now().Unix()%int64(len(instances))]

    url := fmt.Sprintf("http://%s:%d/orders/%s",
        instance.Address, instance.Port, orderID)

    resp, err := http.Get(url)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    return parseOrder(resp)
}
```

---

## Configuration Management

Services need to share configuration across the cluster.

```go
type ConfigManager struct {
    etcd  *clientv3.Client
    cache map[string]string
}

func (cm *ConfigManager) Get(ctx context.Context, key string) (string, error) {
    // Try cache first
    if val, ok := cm.cache[key]; ok {
        return val, nil
    }

    // Fetch from etcd
    resp, err := cm.etcd.Get(ctx, "/config/"+key)
    if err != nil {
        return "", err
    }

    if len(resp.Kvs) == 0 {
        return "", ErrConfigNotFound
    }

    value := string(resp.Kvs[0].Value)
    cm.cache[key] = value

    return value, nil
}

func (cm *ConfigManager) Watch(ctx context.Context, key string, callback func(string)) {
    watchChan := cm.etcd.Watch(ctx, "/config/"+key)

    for {
        select {
        case <-ctx.Done():
            return
        case resp := <-watchChan:
            for _, event := range resp.Events {
                if event.Type == clientv3.EventTypePut {
                    callback(string(event.Kv.Value))
                }
            }
        }
    }
}

// Usage
func (s *PaymentService) Start(ctx context.Context) {
    // Get initial config
    timeout, _ := s.config.Get(ctx, "payment.timeout")
    s.timeout = parseTimeout(timeout)

    // Watch for changes
    s.config.Watch(ctx, "payment.timeout", func(newValue string) {
        s.timeout = parseTimeout(newValue)
        log.Infof("Payment timeout updated to %v", s.timeout)
    })
}
```

---

## Putting It All Together

```go
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

func (cl *CoordinationLayer) LeaderElection(service string) (*LeaderElection, error) {
    return NewLeaderElection(cl.etcd.Endpoints(), "/leadership/"+service)
}

func (cl *CoordinationLayer) DistributedLock(resource string, ttl time.Duration) (*DistributedLock, error) {
    return NewDistributedLock(cl.etcd.Endpoints(), resource, ttl)
}

func (cl *CoordinationLayer) ServiceRegistry() *ServiceRegistry {
    return &ServiceRegistry{etcd: cl.etcd}
}

func (cl *CoordinationLayer) ConfigManager() *ConfigManager {
    return &ConfigManager{etcd: cl.etcd, cache: make(map[string]string)}
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What is service discovery? (Dynamic finding of service instances)
2. How do ephemeral nodes work? (Auto-die when service stops)
3. Why watch for config changes? (Update without restart)
4. How do you load balance across instances? (Round-robin or use LB)

---

**Ready for the complete solution? Read `solution.md`**
