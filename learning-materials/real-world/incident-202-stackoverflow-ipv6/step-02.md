# Step 2: PTR Records and Production IPv6

---

## The PTR Record Problem

**What is reverse DNS?**

```
Forward DNS: name → IP
  stackoverflow.com → 2606:2800:220:1:248:1893:25c8:1946

Reverse DNS: IP → name
  2606:2800:220:1:248:1893:25c8:1946 → stackoverflow.com
```

**Why PTR records matter:**

Many systems perform reverse DNS verification:
- Email servers (spam prevention)
- SSH servers (VerifyReverseDNS)
- Some corporate firewalls
- Network monitoring tools
- Some authentication systems

---

## The Stack Overflow Bug

**Broken PTR:**

```zone
; IPv6 reverse DNS uses ip6.arpa domain
; Format: reverse each hex digit, separate with dots

Original: 2606:2800:220:1:248:1893:25c8:1946
Expanded: 2606:2800:0220:0001:0248:1893:25c8:1946
Reversed:  6491.8c52.3981.8420.1000.0220.0082.6062
Domain:    6491.8c52.3981.8420.1000.0220.0082.6062.ip6.arpa.

; What was configured (WRONG):
server1.stackoverflow.com.  IN  PTR  stackoverflow.com.
; (wrong reverse format, wrong name)

; Should have been:
6.4.9.1.8.c.5.2.3.9.8.1.8.4.2.1.0.0.0.1.0.2.2.0.0.8.2.0.6.2.ip6.arpa.  IN  PTR  stackoverflow.com.
```

**When mismatch occurs:**

```
Client → Server: "Connecting from 2606:..."
Server: "Let me verify that IP..."
Server → DNS: "PTR 2606:..."
DNS: "That's server1.stackoverflow.com"
Server: "But client said it's stackoverflow.com"
Server: "MISMATCH! DROP CONNECTION."
```

---

## Fixing PTR Records

**IPv6 PTR format converter:**

```go
package main

import (
    "fmt"
    "net"
    "strings"
)

func ipv6ToPTR(ipv6 string) (string, error) {
    // Parse IPv6 address
    ip := net.ParseIP(ipv6)
    if ip == nil {
        return "", fmt.Errorf("invalid IPv6 address")
    }

    // Convert to 16-byte representation
    ip = ip.To16()
    if ip == nil {
        return "", fmt.Errorf("not an IPv6 address")
    }

    // Convert to hex string and reverse
    hex := fmt.Sprintf("%032x", ip)
    reversed := reverse(hex)

    // Build PTR record by inserting dots between each nibble
    var ptr strings.Builder
    for i, ch := range reversed {
        if i > 0 {
            ptr.WriteByte('.')
        }
        ptr.WriteByte(byte(ch))
    }
    ptr.WriteString(".ip6.arpa.")

    return ptr.String(), nil
}

func reverse(s string) string {
    runes := []rune(s)
    for i, j := 0, len(runes)-1; i < j; i, j = i+1, j-1 {
        runes[i], runes[j] = runes[j], runes[i]
    }
    return string(runes)
}
```

**Verification script:**

```bash
#!/bin/bash
# verify-ptr.sh

IPV6="2606:2800:220:1:248:1893:25c8:1946"
EXPECTED="stackoverflow.com"

# Query PTR
RESULT=$(dig -x $IPV6 +short)

echo "Expected: $EXPECTED"
echo "Got: $RESULT"

if [ "$RESULT" = "$EXPECTED." ]; then
    echo "✓ PTR correct"
else
    echo "✗ PTR MISMATCH!"
fi
```

---

## Production IPv6 Rollout Strategy

**1. Canary by geography:**

```yaml
# DNS configuration with geo-based steering
# (using Cloudflare, AWS Route53, or similar)

stackoverflow.com:
  - US-East:
      A: 151.101.1.69
      AAAA: 2606:2800:220:1:248:1893:25c8:1946  # Enable IPv6

  - EU-West:
      A: 151.101.65.69
      # AAAA: disabled  # Hold off on IPv6 here

  - AP-Southeast:
      A: 151.101.129.69
      # AAAA: disabled  # Hold off on IPv6 here
```

**2. Gradual rollout:**

```go
package main

import "time"

type IPv6Rollout struct {
    ipv6EnabledRegions map[string]bool
    rolloutOrder       []string
    startTime          time.Time
}

func (r *IPv6Rollout) ShouldEnableIPv6(userRegion string) bool {
    // Gradually enable IPv6 by region
    weeksSinceStart := int(time.Since(r.startTime).Hours() / 24 / 7)

    for i, region := range r.rolloutOrder {
        if region == userRegion {
            return i <= weeksSinceStart
        }
    }
    return false
}

func (r *IPv6Rollout) GetDNSRecords(region string) DNSRecords {
    records := DNSRecords{
        A: r.getIPv4(region),
    }

    if r.ShouldEnableIPv6(region) {
        records.AAAA = r.getIPv6(region)
    }

    return records
}
```

**3. Metrics to monitor:**

```go
type IPv6Metrics struct {
    ConnectionSuccessRate  *prometheus.GaugeVec
    ConnectionLatency      *prometheus.HistogramVec
    TimeoutRate           *prometheus.GaugeVec
    IPv4FallbackRate      *prometheus.GaugeVec
}

func (m *IPv6Metrics) RecordAttempt(protocol string, success bool, latency float64) {
    m.ConnectionLatency.WithLabelValues(protocol).Observe(latency)

    if success {
        m.ConnectionSuccessRate.WithLabelValues(protocol).Set(1)
    } else {
        m.ConnectionSuccessRate.WithLabelValues(protocol).Set(0)
    }
}

// Alert if IPv6 timeout rate > 1%
func CheckIPv6Health(metrics *IPv6Metrics) {
    timeoutRate := getTimeoutRate("ipv6")
    if timeoutRate > 0.01 {
        alert("IPv6 timeout rate exceeds 1%")
    }
}
```

---

## Dual-Stack Application Design

**Application must handle both protocols:**

```go
package main

import (
    "fmt"
    "net"
    "strings"
    "time"
)

func listenDualStack(port int) (*net.TCPListener, *net.TCPListener, error) {
    // Listen on IPv4
    ipv4Addr, err := net.ResolveTCPAddr("tcp4", fmt.Sprintf(":%d", port))
    if err != nil {
        return nil, nil, err
    }

    ipv4Listener, err := net.ListenTCP("tcp4", ipv4Addr)
    if err != nil {
        return nil, nil, err
    }

    // Listen on IPv6
    ipv6Addr, err := net.ResolveTCPAddr("tcp6", fmt.Sprintf(":%d", port))
    if err != nil {
        ipv4Listener.Close()
        return nil, nil, err
    }

    ipv6Listener, err := net.ListenTCP("tcp6", ipv6Addr)
    if err != nil {
        ipv4Listener.Close()
        return nil, nil, err
    }

    return ipv4Listener, ipv6Listener, nil
}

func handleConnection(conn net.Conn) {
    remoteAddr := conn.RemoteAddr().String()

    // Log which protocol was used
    if strings.Contains(remoteAddr, ".") {
        fmt.Printf("IPv4 connection from %s\n", remoteAddr)
    } else {
        fmt.Printf("IPv6 connection from %s\n", remoteAddr)
    }

    // Handle request...
    conn.Close()
}

func main() {
    ipv4, ipv6, err := listenDualStack(443)
    if err != nil {
        fmt.Fprintf(os.Stderr, "Failed to listen: %v\n", err)
        os.Exit(1)
    }
    defer ipv4.Close()
    defer ipv6.Close()

    fmt.Println("Listening on IPv4 and IPv6")

    // Accept from both listeners
    errChan := make(chan error, 2)

    go func() {
        for {
            conn, err := ipv4.AcceptTCP()
            if err != nil {
                errChan <- err
                return
            }
            go handleConnection(conn)
        }
    }()

    go func() {
        for {
            conn, err := ipv6.AcceptTCP()
            if err != nil {
                errChan <- err
                return
            }
            go handleConnection(conn)
        }
    }()

    // Wait for error
    <-errChan
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's reverse DNS (PTR)? (Maps IP addresses back to domain names, used for verification)
2. Why did PTR mismatch cause issues? (Servers verify forward and reverse DNS match, mismatch drops connection)
3. What's the IPv6 PTR format? (Reverse hex nibbles with dots, append .ip6.arpa)
4. How do you roll out IPv6 safely? (Canary by region, monitor metrics, gradual rollout)
5. What's dual-stack networking? (Listening on both IPv4 and IPv6 simultaneously)

---

**Continue to `solution.md`**
