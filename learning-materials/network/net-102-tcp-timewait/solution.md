# Solution: TCP TIME_WAIT

---

## Root Cause

High QPS without connection pooling exhausted ephemeral ports due to TIME_WAIT.

---

## Solution

**Connection pooling (primary):**

```go
// HTTP/2 or gRPC: Single connection, multiplexed requests
// HTTP/1: Connection pool with keep-alive

transport := &http.Transport{
    MaxIdleConns:        100,
    MaxIdleConnsPerHost: 100,
    IdleConnTimeout:     90 * time.Second,
}
client := &http.Client{Transport: transport}
```

**Tuning (secondary):**
```bash
# Increase port range
sysctl -w net.ipv4.ip_local_port_range="1024 65535"

# Allow TIME_WAIT reuse for outgoing connections
sysctl -w net.ipv4.tcp_tw_reuse=1
```

---

**Next Problem:** `network/net-103-tls-handshake/`
