# Solution: IPv6 Dual-Stack Reliability

---

## Root Cause Analysis

**Three issues combined:**

1. **PTR record mismatch** - Reverse DNS didn't match forward DNS
2. **No Happy Eyeballs** - Older clients tried IPv6 sequentially, not in parallel
3. **Firewall asymmetry** - Some networks allowed IPv6 DNS but blocked IPv6 traffic

```
Happy path: Client → IPv6 works ✓

Broken path:
Client → DNS (gets AAAA) → Try IPv6 → Firewall blocks → Timeout → No fallback → Error
```

---

## Complete Solution

### 1. Fix PTR Records

**Automated PTR management:**

```python
import ipaddress
import subprocess
from typing import Dict, Tuple

class DnsManager:
    def __init__(self, bind_zone_file: str, bind_reverse_file: str):
        self.zone_file = bind_zone_file
        self.reverse_file = bind_reverse_file
        self.records: Dict[str, Tuple[str, str]] = {}  # name → (ipv4, ipv6)

    def add_aaaa_record(self, name: str, ipv6: str, ttl: int = 300):
        """Add AAAA record and corresponding PTR."""
        # Validate IPv6
        addr = ipaddress.IPv6Address(ipv6)

        # Add forward record
        forward_entry = f"{name}  IN  AAAA  {ipv6}\n"
        self._append_zone(forward_entry)

        # Create reverse entry
        ptr_name = self._ipv6_to_ptr(ipv6)
        reverse_entry = f"{ptr_name}  IN  PTR  {name}.\n"
        self._append_reverse(reverse_entry)

        # Reload BIND
        self._reload_dns()

    def _ipv6_to_ptr(self, ipv6: str) -> str:
        """Convert IPv6 to PTR record name."""
        addr = ipaddress.IPv6Address(ipv6)
        expanded = addr.exploded
        reversed_hex = expanded.replace(':', '')[::-1]
        return '.'.join(reversed_hex) + '.ip6.arpa.'

    def verify_ptr(self, ipv6: str, expected_name: str) -> bool:
        """Verify PTR record matches expected name."""
        try:
            result = subprocess.run(
                ['dig', '-x', ipv6, '+short'],
                capture_output=True, text=True, timeout=5
            )
            actual = result.stdout.strip().rstrip('.')
            return actual == expected_name
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _append_zone(self, entry: str):
        with open(self.zone_file, 'a') as f:
            f.write(entry)

    def _append_reverse(self, entry: str):
        with open(self.reverse_file, 'a') as f:
            f.write(entry)

    def _reload_dns(self):
        subprocess.run(['rndc', 'reload'], check=True)

# Usage
dns = DnsManager('/etc/bind/db.stackoverflow.com',
                 '/etc/bind/db.stackoverflow.reverse')
dns.add_aaaa_record('stackoverflow.com', '2606:2800:220:1:248:1893:25c8:1946')
assert dns.verify_ptr('2606:2800:220:1:248:1893:25c8:1946', 'stackoverflow.com')
```

### 2. Client-Side Happy Eyeballs

**Production-ready implementation:**

```go
package netutil

import (
    "context"
    "net"
    "sync"
    "time"
)

// HappyEyeballs connects to hostname using IPv4 and IPv6 in parallel.
// Returns whichever connection succeeds first.
func HappyEyeballs(ctx context.Context, hostname string, port string) (net.Conn, error) {
    // DNS resolution with both A and AAAA
    ipv4Addrs, ipv6Addrs, err := resolveBoth(hostname, port)
    if err != nil {
        return nil, err
    }

    // No addresses
    if len(ipv4Addrs) == 0 && len(ipv6Addrs) == 0 {
        return nil, &net.DNSError{Err: "no addresses found"}
    }

    // Result channel
    type result struct {
        conn net.Conn
        err  error
    }
    results := make(chan result, 2)

    // Context for cancellation
    dialCtx, cancel := context.WithCancel(ctx)
    defer cancel()

    var wg sync.WaitGroup

    // Try IPv6 first (with short timeout)
    if len(ipv6Addrs) > 0 {
        wg.Add(1)
        go func() {
            defer wg.Done()
            dialer := &net.Dialer{
                Timeout:   300 * time.Millisecond, // Short timeout for IPv6
                KeepAlive: 30 * time.Second,
            }

            for _, addr := range ipv6Addrs {
                conn, err := dialer.DialContext(dialCtx, "tcp6", addr)
                if err == nil {
                    select {
                    case results <- result{conn: conn}:
                    case <-dialCtx.Done():
                        conn.Close()
                    }
                    return
                }
            }
        }()
    }

    // Start IPv4 after delay (only if IPv6 hasn't connected)
    if len(ipv4Addrs) > 0 {
        wg.Add(1)
        go func() {
            defer wg.Done()

            // Wait a bit for IPv6 to try
            time.Sleep(300 * time.Millisecond)

            dialer := &net.Dialer{
                Timeout:   10 * time.Second,
                KeepAlive: 30 * time.Second,
            }

            for _, addr := range ipv4Addrs {
                conn, err := dialer.DialContext(dialCtx, "tcp4", addr)
                if err == nil {
                    select {
                    case results <- result{conn: conn}:
                    case <-dialCtx.Done():
                        conn.Close()
                    }
                    return
                }
            }
        }()
    }

    // Wait for first success or all failures
    go func() {
        wg.Wait()
        close(results)
    }()

    // Return first successful connection
    for res := range results {
        if res.conn != nil {
            return res.conn, nil
        }
    }

    return nil, &net.OpError{Err: "all connection attempts failed"}
}

func resolveBoth(hostname, port string) (ipv4, ipv6 []string, err error) {
    addrs, err := net.LookupHost(hostname)
    if err != nil {
        return nil, nil, err
    }

    for _, addr := range addrs {
        if ip := net.ParseIP(addr); ip != nil {
            if ip.To4() == nil {
                // IPv6
                ipv6 = append(ipv6, net.JoinHostPort(addr, port))
            } else {
                // IPv4
                ipv4 = append(ipv4, net.JoinHostPort(addr, port))
            }
        }
    }

    return ipv4, ipv6, nil
}
```

### 3. Gradual IPv6 Rollout

**Feature flag system:**

```yaml
# ipv6_rollout.yaml
flags:
  ipv6_enabled:
    default: false
    rules:
      # Enable by region
      - if: user.region in ["us-east", "us-west"]
        then: true
        percentage: 100

      # Canary in EU
      - if: user.region == "eu-west"
        then: true
        percentage: 10  # 10% of EU users

      # Disabled elsewhere
      - if: true
        then: false
```

```python
class IPv6Config:
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)

    def is_ipv6_enabled(self, user_context: dict) -> bool:
        """Check if IPv6 should be enabled for this user."""
        for rule in self.config['flags']['ipv6_enabled']['rules']:
            if self._matches_rule(user_context, rule):
                # Apply percentage rollout
                if 'percentage' in rule:
                    user_hash = hash(user_context['user_id']) % 100
                    return user_hash < rule['percentage']
                return rule['then']
        return self.config['flags']['ipv6_enabled']['default']

    def get_dns_answers(self, user_context: dict) -> list:
        """Return DNS answers based on IPv6 flag."""
        answers = [
            {'type': 'A', 'address': '151.101.1.69'}
        ]

        if self.is_ipv6_enabled(user_context):
            answers.append({
                'type': 'AAAA',
                'address': '2606:2800:220:1:248:1893:25c8:1946'
            })

        return answers
```

### 4. Monitoring and Testing

**Pre-deployment validation:**

```bash
#!/bin/bash
# ipv6_validation.sh - Run before deploying to production

set -e

DOMAIN="stackoverflow.com"
EXPECTED_IPV6="2606:2800:220:1:248:1893:25c8:1946"
EXPECTED_PTR="stackoverflow.com"

echo "=== IPv6 Pre-Deployment Validation ==="

# 1. Check AAAA record exists
echo -n "1. AAAA record... "
AAAA=$(dig AAAA +short $DOMAIN)
if [ -z "$AAAA" ]; then
    echo "FAIL: No AAAA record"
    exit 1
fi
echo "OK: $AAAA"

# 2. Verify IPv6 is reachable
echo -n "2. IPv6 connectivity... "
if ping6 -c 1 -W 2 $EXPECTED_IPV6 >/dev/null 2>&1; then
    echo "OK"
else
    echo "FAIL: Cannot ping IPv6 address"
    exit 1
fi

# 3. Verify TCP connection works
echo -n "3. TCP port 443... "
if timeout 5 nc -6zv $EXPECTED_IPV6 443 2>&1 | grep -q succeeded; then
    echo "OK"
else
    echo "FAIL: Cannot connect to IPv6:443"
    exit 1
fi

# 4. Verify PTR record
echo -n "4. PTR record... "
PTR=$(dig -x $EXPECTED_IPV6 +short | sed 's/\.$//')
if [ "$PTR" = "$EXPECTED_PTR" ]; then
    echo "OK"
else
    echo "FAIL: PTR mismatch (got: $PTR, expected: $EXPECTED_PTR)"
    exit 1
fi

# 5. Test Happy Eyeballs behavior
echo -n "5. Happy Eyeballs test... "
# Use curl with IPv6 prefered but IPv4 fallback
if curl -6 -s -o /dev/null -w "%{http_code}" --connect-timeout 5 https://$DOMAIN | grep -q "200\|000"; then
    echo "OK"
else
    echo "WARN: IPv6 connection failed, checking IPv4..."
    if curl -4 -s -o /dev/null -w "%{http_code}" --connect-timeout 5 https://$DOMAIN | grep -q "200"; then
        echo "IPv4 OK, IPv6 issue detected"
    else
        echo "FAIL: Neither IPv4 nor IPv6 works"
        exit 1
    fi
fi

# 6. Test from multiple vantage points
echo "6. External vantage points..."
VANTAGE_POINTS=(
    "https://ipv6-test.com/api/myip.php"
    "https://dns.google/resolve"
)

for vp in "${VANTAGE_POINTS[@]}"; do
    echo -n "  Testing $vp... "
    if curl -s --max-time 5 "$vp" >/dev/null; then
        echo "OK"
    else
        echo "WARN: Failed to reach vantage point"
    fi
done

echo "=== All validations passed ==="
```

---

## Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| **Enable IPv6 immediately** | All users benefit | Risk of breaking some networks |
| **Gradual rollout** | Risk mitigation, metrics-driven | Complex configuration |
| **AAAA with low TTL** | Quick rollback | More DNS queries |
| **Separate IPv6 domain** | Isolation, easy testing | Not standard, confusing |

**Recommendation:** Gradual rollout with feature flags, monitor metrics closely.

---

## Real Incident: Stack Overflow 2017

**What happened:**
- Enabled IPv6 AAAA records
- PTR records had mismatch (wrong format)
- Some networks had IPv6 DNS but blocked IPv6 traffic
- Clients without Happy Eyeballs hung on IPv6 timeout
- No fallback to IPv4

**What changed:**
- Fixed PTR records to match forward DNS
- Implemented Happy Eyeballs in application layer
- Added IPv6 connectivity monitoring
- Gradual rollout by geography

**Postmortem quote:**
> "IPv6 is not 'IPv4 with longer addresses.' It's a different protocol with different failure modes."

---

## IPv6 Checklist

**Before enabling IPv6:**
- [ ] AAAA records added to DNS
- [ ] PTR records created and verified
- [ ] Firewall allows IPv6 traffic (all required ports)
- [ ] Application listens on IPv6 socket
- [ ] Happy Eyeballs implemented or verified
- [ ] Monitoring for IPv6-specific metrics
- [ ] Rollback plan (remove AAAA records)
- [ ] Test from multiple network types
- [ ] Gradual rollout strategy defined

**Ongoing:**
- [ ] Monitor IPv6 vs IPv4 connection rates
- [ ] Track IPv6 timeout/fallback rates
- [ ] Regular PTR verification
- [ ] Test from various client networks

---

**Next Problem:** `real-world/incident-203-gitlab-rm-rf/`
