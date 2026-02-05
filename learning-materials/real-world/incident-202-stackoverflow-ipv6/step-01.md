# Step 1: Happy Eyeballs and Connection Race

---

## The IPv6 Preference Problem

**Clients prefer IPv6 by default:**

```python
# RFC 6555 - Happy Eyeballs (before)
def connect_old(hostname):
    # DNS resolution
    results = getaddrinfo(hostname, 443)

    # Sort: IPv6 addresses first, IPv4 after
    results.sort(key=lambda r: 0 if r[0] == AF_INET6 else 1)

    # Try each address sequentially
    for family, addr in results:
        try:
            return socket.create_connection(addr, timeout=30)
        except:
            continue

    raise ConnectionError("All addresses failed")
```

**Problem:** If IPv6 hangs (doesn't fail fast), you wait 30 seconds before trying IPv4!

---

## Happy Eyeballs Algorithm

**Race both protocols:**

```python
import socket
import threading
import time

def connect_happy_eyeballs(hostname, port=443, ipv6_timeout=0.3):
    """
    Happy Eyeballs: Try IPv6 and IPv4 in parallel,
    use whichever connects first.
    """
    # Resolve both address types
    try:
        results = socket.getaddrinfo(hostname, port)
    except socket.gaierror:
        raise ConnectionError(f"DNS resolution failed for {hostname}")

    # Separate IPv4 and IPv6 addresses
    ipv6_addrs = [addr for family, _, _, _, addr in results if family == socket.AF_INET6]
    ipv4_addrs = [addr for family, _, _, _, addr in results if family == socket.AF_INET]

    if not ipv4_addrs and not ipv6_addrs:
        raise ConnectionError("No addresses resolved")

    result = {'sock': None, 'done': False}

    def try_connect(addresses, is_ipv6):
        for addr in addresses:
            if result['done']:
                return

            sock = socket.socket(socket.AF_INET6 if is_ipv6 else socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5 if is_ipv6 else 10)  # Shorter timeout for IPv6

            try:
                start = time.time()
                sock.connect(addr)
                elapsed = time.time() - start

                if not result['done']:
                    result['sock'] = sock
                    result['done'] = True
                    print(f"Connected via {'IPv6' if is_ipv6 else 'IPv4'} in {elapsed:.3f}s")
                    return
            except (socket.timeout, ConnectionRefusedError, OSError):
                sock.close()
                if is_ipv6:
                    # IPv6 failed quickly, signal to start IPv4 immediately
                    time.sleep(0)  # Yield
                continue

    # Start IPv6 connection attempt
    if ipv6_addrs:
        ipv6_thread = threading.Thread(target=try_connect, args=(ipv6_addrs, True))
        ipv6_thread.start()

        # Wait for IPv6 timeout, then start IPv4
        ipv6_thread.join(timeout=ipv6_timeout)

        if not result['done'] and ipv4_addrs:
            # IPv6 didn't connect in time, try IPv4
            ipv4_thread = threading.Thread(target=try_connect, args=(ipv4_addrs, False))
            ipv4_thread.start()
            ipv4_thread.join(timeout=10)
    else:
        # No IPv6, just try IPv4
        try_connect(ipv4_addrs, False)

    # Give a bit more time for threads to complete
    time.sleep(0.1)

    if result['sock']:
        return result['sock']
    else:
        raise ConnectionError("Failed to connect via any protocol")
```

**Key insight:** Start IPv6, but if it doesn't connect within 300ms, start IPv4 in parallel. Use whichever wins.

---

## Why Some Clients Didn't Fallback

**RFC 3484 (default address selection):**

```
Priority order:
1. IPv6 with IPv6 source address
2. IPv4 with IPv6 source address (IPv4-mapped)
3. IPv6 with IPv4 source address
4. IPv4 with IPv4 source address
```

**Older implementations:**
- Try all IPv6 addresses first (can be multiple)
- Each IPv6 attempt can take 30+ seconds
- Only then try IPv4
- Result: 60-90 second timeout

**Modern implementations (Happy Eyeballs v2):**
- Start IPv6 and IPv4 in parallel (staggered by 100-300ms)
- Use whichever connects first
- Cancel the loser

---

## DNS Resolution Behavior

```python
# What getaddrinfo() returns
>>> socket.getaddrinfo("stackoverflow.com", 443)
[
    (AF_INET6, SOCK_STREAM, IPPROTO_TCP, '', ('2606:2800:220:1:248:1893:25c8:1946', 443, 0, 0)),
    (AF_INET, SOCK_STREAM, IPPROTO_TCP, '', ('151.101.1.69', 443))
]

# Clients iterate this list in order
```

**The connection flow:**

```
Client                 IPv6 Network              IPv4 Network
  │                         │                          │
  │──── SYN IPv6 ──────────→│                          │
  │                         │── BLOCKED BY FIREWALL ───│
  │                         │                          │
  │ (waits 30s)             │                          │
  │                         │                          │
  │ (maybe try IPv4?)       │                          │
  │──── SYN IPv4 ───────────┼─────────────────────────→│
  │                         │                          │
  │ ✓ Connected             │                          │
```

---

## Testing IPv6 Before Deploy

**Pre-deployment checklist:**

```bash
#!/bin/bash
# ipv6-readiness-check.sh

echo "Testing IPv6 connectivity..."

# 1. Can we resolve AAAA records?
echo "1. Checking AAAA record..."
dig AAAA stackoverflow.com +short

# 2. Can we ping the IPv6 address?
echo "2. Pinging IPv6 address..."
ping6 -c 3 2606:2800:220:1:248:1893:25c8:1946

# 3. Can we connect over IPv6?
echo "3. Testing IPv6 TCP connection..."
timeout 5 nc -6 -z -v 2606:2800:220:1:248:1893:25c8:1946 443

# 4. Verify reverse DNS
echo "4. Checking reverse DNS (PTR)..."
dig -x 2606:2800:220:1:248:1893:25c8:1946 +short

# 5. Test from various networks
echo "5. Testing from multiple vantage points..."
# Use external services like:
# - https://ipv6-test.com/
# - https://dns.google/
# - curl from different VPNs/regions

# 6. Verify firewall allows IPv6
echo "6. Checking firewall rules..."
ip6tables -L -n | grep 443

# 7. Test Happy Eyeballs behavior
echo "7. Testing fallback behavior..."
# Use tool like: https://github.com/libhappy/happy-eyeballs
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's Happy Eyeballs? (Race IPv6 and IPv4 connections, use whichever connects first)
2. Why did IPv6 cause issues? (Clients try IPv6 first, if it hangs, delayed IPv4 attempt)
3. What's the timeout problem? (Old clients try all IPv6 addresses sequentially, each can take 30s)
4. How does Happy Eyeballs solve it? (Start IPv6, if no connect in 300ms, start IPv4 in parallel)
5. What's getaddrinfo? (DNS resolution function that returns sorted list of addresses)

---

**Continue to `step-02.md`
