# Step 2: Failover Strategy and DNS

---

## The Failure: DNS as Coordination Mechanism

GitHub used DNS to point to database IP. This created a dependency:

```
Failover requires:
1. Database reconfiguration
2. HAProxy reconfiguration
3. DNS update
4. App servers to refresh DNS cache (PROBLEM!)
5. App connection pools to refresh (PROBLEM!)
```

**DNS is not a reliable coordination mechanism!** Caching prevents immediate propagation.

---

## Better Approach: Virtual IP (VIP)

```
┌─────────────────────────────────────────────────────────────┐
│                       VIP: 10.0.0.1                         │
│              (Never changes, always points to current)       │
└────────────────────────┬────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          │   Keepalived (VRRP)        │
          │   Monitors primary health  │
          │   Moves VIP if needed      │
          └──────────────┬──────────────┘
                         │
          ┌──────────────┴──────────────┐
          │                             │
          ▼                             ▼
┌─────────────────────┐         ┌─────────────────────┐
│   Primary (10.0.2.1)  │         │   Replica (10.0.3.1) │
│   VIP: 10.0.0.1      │         │   (standby)          │
└─────────────────────┘         └─────────────────────┘
```

**VIP never changes!** App servers always connect to `10.0.0.1`. Keepalived moves VIP to healthy node.

---

## Connection Pool Invalidation

```go
type FailoverAwarePool struct {
    mu       sync.RWMutex
    currentDSN string
    pool     *sql.DB
}

func (p *FailoverAwarePool) Conn() (*sql.Conn, error) {
    for {
        p.mu.RLock()
        dsn := p.currentDSN
        db := p.pool
        p.mu.RUnlock()

        conn, err := db.Conn()
        if err == nil {
            return conn, nil
        }

        // Connection failed - might be failover
        p.invalidate()

        // Refresh and retry
        time.Sleep(100 * time.Millisecond)
    }
}

func (p *FailoverAwarePool) invalidate() {
    p.mu.Lock()
    defer p.mu.Unlock()

    // Close old pool
    p.pool.Close()

    // Get new DNS
    newIP := resolveDNS("db-0.primary.github.net")
    p.currentDSN = fmt.Sprintf("user@%s:3306/db", newIP)

    // Create new pool
    p.pool = sql.Open("mysql", p.currentDSN)
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's a Virtual IP (VIP)? (IP that never changes, moves between nodes via VRRP/Keepalived)
2. How does VIP solve the DNS caching problem? (App connects to same IP, VIP moves to healthy node automatically)
3. What's failover-aware connection pool? (Detects connection failures, invalidates pool, reconnects with fresh DNS)
4. Why is VIP better than DNS for failover? (No caching issues, immediate failover, app unaware of changes)
5. What's the pattern for connection pool invalidation? (On connection failure, close pool, refresh DNS, create new pool)

---

**Continue to `solution.md`
