# Solution: DNS Migrations

---

## Root Cause

High TTL (24h) caused DNS caching. Connection pools compounded the issue.

---

## Solution

**Proper migration:**

1. **Pre-migration:** Lower TTL to 60s (24h before)
2. **During migration:** Add both old and new IPs to DNS
3. **Keep old servers running** until traffic shifts
4. **Monitor** traffic to old servers
5. **Post-migration:** Raise TTL back to normal

**Connection pool refresh:**
```go
// Periodically close connections to force DNS refresh
go func() {
    for range time.Tick(time.Minute) {
        connPool.CloseIdleConnections()
    }
}()
```

---

**Next Problem:** `network/net-102-tcp-timewait/`
