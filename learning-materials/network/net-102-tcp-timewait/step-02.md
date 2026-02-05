# Step 2: Solutions

---

## Solution 1: Connection Pooling (Best)

```go
// Reuse connections instead of new per request
type Pool struct {
    conns chan *Conn
    dialer func() (*Conn, error)
}

func (p *Pool) Get() (*Conn, error) {
    select {
    case conn := <-p.conns:
        return conn, nil
    default:
        return p.dialer()
    }
}

func (p *Pool) Put(conn *Conn) {
    select {
    case p.conns <- conn:
    default:
        conn.Close()  // Pool full, close
    }
}
```

---

## Solution 2: Increase Port Range

```bash
# Linux
echo "1024 65535" > /proc/sys/net/ipv4/ip_local_port_range

# Or sysctl
net.ipv4.ip_local_port_range = 1024 65535
```

---

## Solution 3: Reduce TIME_WAIT (Not Recommended)

```bash
# Reduce MSL (risky!)
net.ipv4.tcp_tw_reuse = 1  # Allow reuse for new connections
net.ipv4.tcp_fin_timeout = 15  # Reduce from 60 to 15 seconds
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's the best solution for TIME_WAIT exhaustion? (Connection pooling - reuse connections)
2. How do you increase ephemeral port range? (sysctl net.ipv4.ip_local_port_range = 1024 65535)
3. What's tcp_tw_reuse? (Allow reuse for new connections - can be risky)
4. What's tcp_fin_timeout? (Reduce TIME_WAIT duration - not recommended, breaks protocol)
5. Why is connection pooling better than tuning kernel? (Avoids creating new connections per request)

---

**Read `solution.md`
