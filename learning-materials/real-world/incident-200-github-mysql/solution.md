# Solution: GitHub MySQL Failover - DNS Caching Disaster

---

## Root Cause Analysis

**Three layers of caching prevented immediate failover:**

1. **DNS caching** (TTL = 60 seconds) - App servers cached old IP
2. **Connection pools** (pool size = 100) - Established connections never refreshed
3. **Driver connection caching** - MySQL driver reusing existing connections

```
Failover timeline:
T+0s:     Detect primary failure
T+5s:     Update HAProxy to point to replica
T+10s:    Update DNS (60s TTL, but caches ignore TTL!)
T+60s:    DNS TTL expires (in theory)
T+300s:   Some app servers still using old IP (cache ignored TTL!)
T+420min: Outage ends after manual app server restart
```

---

## Complete Solution

### 1. Virtual IP (VIP) with Keepalived

**VIP eliminates DNS from failover path:**

```
┌─────────────────────────────────────────────────────────────┐
│                  Application Servers                        │
│                  (always connect to VIP)                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                       VIP: 10.0.0.1                         │
│                  (moves between nodes)                      │
└────────────────────────┬────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          │   Keepalived (VRRP)        │
          │   Priority: Primary=100    │
          │             Replica=90     │
          │   advert_int 1s            │
          │   master_down 3s           │
          └──────────────┬──────────────┘
                         │
          ┌──────────────┴──────────────┐
          │                             │
          ▼                             ▼
┌─────────────────────┐         ┌─────────────────────┐
│   Primary           │         │   Replica           │
│   Real IP: 10.0.2.1 │         │   Real IP: 10.0.3.1 │
│   VIP: 10.0.0.1 ✓   │         │   VIP: (standby)    │
│   MySQL: RUNNING    │         │   MySQL: RUNNING    │
└─────────────────────┘         └─────────────────────┘
```

**Keepalived configuration:**

```bash
# On primary (/etc/keepalived/keepalived.conf)
vrrp_instance MYSQL_VIP {
    state MASTER
    interface eth0
    virtual_router_id 51
    priority 100
    advert_int 1

    authentication {
        auth_type PASS
        auth_pass mysql_failover_secret
    }

    virtual_ipaddress {
        10.0.0.1/24
    }

    track_script {
        chk_mysql
    }
}

vrrp_script chk_mysql {
    script "/usr/local/bin/check_mysql.sh"
    interval 2
    weight -50
    fall 2
    rise 2
}
```

```bash
# On replica
vrrp_instance MYSQL_VIP {
    state BACKUP
    interface eth0
    virtual_router_id 51
    priority 90
    advert_int 1
    # ... same authentication and VIP ...
}
```

**MySQL health check:**

```bash
#!/bin/bash
# /usr/local/bin/check_mysql.sh

MYSQL_HOST="127.0.0.1"
MYSQL_PORT="3306"
MYSQL_USER="health_check"
MYSQL_PASS="health_check_password"

# Check if MySQL responds to PING
mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" \
      -u "$MYSQL_USER" -p"$MYSQL_PASS" \
      -e "SELECT 1" >/dev/null 2>&1

if [ $? -eq 0 ]; then
    # Check if this is the PRIMARY (read_only=OFF)
    READ_ONLY=$(mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" \
                     -u "$MYSQL_USER" -p"$MYSQL_PASS" \
                     -Ne "SELECT @@read_only" 2>/dev/null)

    if [ "$READ_ONLY" = "0" ]; then
        exit 0  # Primary is healthy
    else
        exit 1  # Not primary anymore
    fi
else
    exit 1  # MySQL not responding
fi
```

**Failover behavior with VIP:**

```
T+0s:     Primary crashes
T+2s:     Keepalived detects failure (2 checks x 2s interval)
T+3s:     Replica sees 3 adverts missed (master_down 3s)
T+5s:     VIP moves to replica ( Gratuitous ARP sent)
T+5s:     App servers detect route change via ARP
T+5s:     New connections go to replica (former primary)

Total failover: ~5 seconds
```

---

### 2. Connection Pool Invalidation

**Problem:** Even with VIP, existing connections in pool are dead.

**Solution:** Failover-aware connection pool:

```go
package database

import (
    "context"
    "database/sql"
    "fmt"
    "net"
    "sync"
    "time"
)

type FailoverAwarePool struct {
    mu            sync.RWMutex
    dsn           string
    vip           string
    db            *sql.DB
    lastFailover  time.Time
    probeInterval time.Duration
}

func NewFailoverAwarePool(vip, dsn string) (*FailoverAwarePool, error) {
    pool := &FailoverAwarePool{
        vip:           vip,
        dsn:           dsn,
        probeInterval: 5 * time.Second,
    }

    if err := pool.connect(); err != nil {
        return nil, err
    }

    // Start background health probe
    go pool.healthProbe()

    return pool, nil
}

func (p *FailoverAwarePool) connect() error {
    p.mu.Lock()
    defer p.mu.Unlock()

    db, err := sql.Open("mysql", p.dsn)
    if err != nil {
        return err
    }

    // Configure pool for rapid failure detection
    db.SetMaxOpenConns(100)
    db.SetMaxIdleConns(10)
    db.SetConnMaxLifetime(30 * time.Second)  // Force rotation
    db.SetConnMaxIdleTime(10 * time.Second)
    db.SetConnDeadline(1 * time.Second)      // Fail fast

    p.db = db
    return nil
}

func (p *FailoverAwarePool) Conn(ctx context.Context) (*sql.Conn, error) {
    // First, try to get existing connection
    p.mu.RLock()
    db := p.db
    p.mu.RUnlock()

    conn, err := db.Conn(ctx)
    if err == nil {
        // Verify connection is alive
        if err := conn.PingContext(ctx); err == nil {
            return conn, nil
        }
        conn.Close()
    }

    // Connection failed - trigger failover recovery
    p.invalidate()

    // Retry with new pool
    return p.retryConn(ctx)
}

func (p *FailoverAwarePool) retryConn(ctx context.Context) (*sql.Conn, error) {
    for i := 0; i < 3; i++ {
        p.mu.RLock()
        db := p.db
        p.mu.RUnlock()

        conn, err := db.Conn(ctx)
        if err == nil {
            if err := conn.PingContext(ctx); err == nil {
                return conn, nil
            }
            conn.Close()
        }

        // Backoff before retry
        select {
        case <-ctx.Done():
            return nil, ctx.Err()
        case <-time.After(time.Duration(i+1) * 100 * time.Millisecond):
        }
    }

    return nil, fmt.Errorf("failed to establish connection after failover")
}

func (p *FailoverAwarePool) invalidate() {
    p.mu.Lock()
    defer p.mu.Unlock()

    // Close existing pool
    if p.db != nil {
        p.db.Close()
    }

    // Create new pool
    p.connect()
    p.lastFailover = time.Now()
}

func (p *FailoverAwarePool) healthProbe() {
    ticker := time.NewTicker(p.probeInterval)
    defer ticker.Stop()

    for range ticker.C {
        ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
        conn, err := p.Conn(ctx)
        cancel()

        if err != nil {
            // Health check failed - log and continue
            // invalidate() will be called by next query
            continue
        }

        // Check if this is still the primary
        var readOnly bool
        err = conn.QueryRowContext(context.Background(),
            "SELECT @@read_only").Scan(&readOnly)
        conn.Close()

        if err != nil || readOnly {
            // We're connected to replica!
            p.invalidate()
        }
    }
}

// Check if VIP has moved (network-level probe)
func (p *FailoverAwarePool) probeVIP() bool {
    conn, err := net.DialTimeout("tcp", fmt.Sprintf("%s:3306", p.vip), 2*time.Second)
    if err != nil {
        return false
    }
    conn.Close()
    return true
}
```

---

### 3. DNS Configuration for Fallback

**Even with VIP, configure DNS properly:**

```bash
# Pre-failover: Lower TTL gradually
# 1 week before: 3600 → 1800 → 300 → 60

# zone file
$TTL 60
db-primary.github.net. IN A 10.0.0.1  ; VIP

# During failover: No change! VIP stays same
# DNS becomes irrelevant
```

**Key insight:** With VIP, DNS is only for initial discovery. VIP never changes.

---

### 4. Application-Level Failover

**Using MySQL driver with automatic failover:**

```go
// Go MySQL driver with failover
dsn := fmt.Sprintf(
    "%s:%s@tcp(%s:3306)/%s?timeout=5s&readTimeout=5s&writeTimeout=5s&interpolateParams=true",
    user, password, vip, database,
)

db, err := sql.Open("mysql", dsn)

// Enable TCP keepalive to detect dead connections faster
db.SetConnMaxLifetime(30 * time.Second)
```

---

## Trade-offs

| Approach | Failover Time | Complexity | Single Point of Failure? |
|----------|---------------|------------|--------------------------|
| **DNS update** | 60s+ (in practice, hours) | Low | DNS servers |
| **VIP (VRRP)** | ~5s | Medium | Keepalived (but active on both) |
| **Proxy (HAProxy)** | ~2s | High | HAProxy (need active-active) |
| **Client-side discovery** | ~10s | High | Discovery service |

**Recommendation:** VIP with Keepalived for database failover. Add HAProxy only if you need connection pooling at proxy layer.

---

## Real Incident: GitHub 2022

**What happened:**
- GitHub attempted MySQL failover during maintenance
- DNS caching + connection pools caused app servers to connect to old primary IP for 7 hours
- Manual restart of app servers required

**What changed:**
- Adopted VIP-based failover
- Implemented connection pool health checks
- Added automated failover testing

**Postmortem quote:**
> "DNS is not a coordination mechanism. Caching exists at multiple layers and doesn't respect TTL during outages."

---

## Detection and Prevention

**Monitoring:**

```go
// Track failover events
type FailoverMetric struct {
    Timestamp      time.Time
    OldPrimary     string
    NewPrimary     string
    Duration       time.Duration
    ManualTrigger  bool
}

// Alert on long failovers
if failoverDuration > 30*time.Second {
    alert.Send("Database failover took longer than 30s")
}

// Track connection pool errors
poolErrors.Observe(float64(errors), "pool", "connection_failed")
```

**Testing:**

```bash
#!/bin/bash
# chaos_test.sh - Test failover regularly

echo "Starting failover test..."

# Record start time
START=$(date +%s)

# Trigger failover (stop MySQL on primary)
ssh primary-db "systemctl stop mysql"

# Wait for VIP to move
while ! mysql -h $VIP -e "SELECT 1" 2>/dev/null; do
    sleep 0.5
done

END=$(date +%s)
DURATION=$((END - START))

echo "Failover completed in ${DURATION}s"

# Restore
ssh primary-db "systemctl start mysql"

# Alert if too slow
if [ $DURATION -gt 10 ]; then
    echo "WARNING: Failover took ${DURATION}s (threshold: 10s)"
fi
```

---

**Next Problem:** `real-world/incident-201-cloudflare-bgp/`
