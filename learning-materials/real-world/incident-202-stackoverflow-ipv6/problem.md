---
name: incident-202-stackoverflow-ipv6
description: System design problem
difficulty: Advanced
category: Real-World / Networking / DNS / IPv6
level: Senior Engineer
---
# Real-World 202: Stack Overflow IPv6 Outage

---

## The Situation

You're a Senior Engineer at Stack Overflow. Your site works perfectly over IPv4. You've recently enabled IPv6 and things seem to work... until reports come in.

**The Setup:**

```
Stack Overflow Infrastructure:
- Web servers: Dual-stack (IPv4 + IPv6)
- IPv4: 151.101.1.69 (working perfectly)
- IPv6: 2606:2800:220:1:248:1893:25c8:1946 (newly enabled)
- DNS: AAAA record added for stackoverflow.com
```

**DNS Configuration:**

```zone
; stackoverflow.com zone file
stackoverflow.com.  IN  A      151.101.1.69
stackoverflow.com.  IN  AAAA   2606:2800:220:1:248:1893:25c8:1946

; Reverse DNS (PTR records)
; IPv4 PTR (working)
69.1.101.151.in-addr.arpa.  IN  PTR  stackoverflow.com.

; IPv6 PTR (problematic!)
; IPv6 addresses use nibble format (reverse hex digits)
6.4.9.1.8.c.5.2.3.9.8.1.8.4.2.0.1.0.0.0.1.0.2.2.0.0.8.2.0.6.2.ip6.arpa.  IN  PTR  server1.stackoverflow.com.
```

---

## The Incident

```
Date: July 2017
Duration: 6 hours
Impact: Some users unable to access Stack Overflow

Symptoms:
- "Connection timeout" errors from certain networks
- Affects users on corporate networks, universities
- Mobile networks work fine
- Home networks work fine
- IPv4-only clients work fine

Affected users report:
- Browser hangs for 30 seconds then shows error
- Can't ping stackoverflow.com
- curl: "Failed to connect to 2606:2800:220:1:248:1893:25c8:1946: Connection timed out"
```

---

## The Jargon

| Term | Definition | Analogy |
|------|------------|---------|
| **AAAA record** | DNS record for IPv6 address (quad-A = 4x A) | Phone number's country extension |
| **PTR record** | Reverse DNS (IP → name) | Caller ID showing who's calling |
| **Dual-stack** | Device has both IPv4 and IPv6 | Having both landline and cell phone |
| **Happy Eyeballs** | Algorithm to race IPv4 and IPv6 connections | Trying both doors, entering whichever opens first |
| **Prefix delegation** | ISP assigns IPv6 prefix to customer | ISP gives you a range of phone numbers |
| **Nibble format** | IPv6 reverse DNS format (each hex digit = label) | Spelling phone number backwards, digit by digit |
| **RA (Router Advertisement)** | IPv6 equivalent of DHCP | Router announces "I'm here, here's your config" |
| **SLAAC** | Stateless Address Auto Configuration | Device picks its own address from prefix |
| **/firewall block** | IPv6 firewall rules often missing | "We locked the back door but forgot the side gate" |

---

## What Happened

**The bug:**

When IPv6 was enabled, some corporate networks had IPv6 configured but **blocked** at their firewall. The DNS returned AAAA record, clients tried IPv6, connection timed out, but **fallback to IPv4 never happened**.

```python
# Browser connection attempt (pseudo-code)
def connect(hostname):
    # DNS resolution returns both A and AAAA
    ipv4 = resolve_A(hostname)    # 151.101.1.69
    ipv6 = resolve_AAAA(hostname) # 2606:2800:220:1:...

    # Try IPv6 first (Happy Eyeballs prefers IPv6)
    try:
        sock = socket.create_connection((ipv6, 443), timeout=0.3)
        return sock
    except TimeoutError:
        # SHOULD try IPv4 here...
        # But some older implementations don't!
        raise ConnectionError("Failed to connect")
```

**The real issue:** The reverse DNS (PTR record) for the IPv6 address pointed to `server1.stackoverflow.com` instead of `stackoverflow.com`. Some security systems perform reverse DNS verification and block mismatches.

---

## The Timeline

```
T+0h:   IPv6 enabled, AAAA record added
T+1h:   First support tickets: "Can't access from office"
T+2h:   Pattern emerges: corporate networks affected
T+3h:   Investigation: IPv6 timeout, no IPv4 fallback
T+4h:   Root cause: PTR record mismatch + client behavior
T+6h:   Fix: Remove AAAA record temporarily
T+8h:   Proper fix: Correct PTR record + Happy Eyeballs investigation
```

---

## Why It Worked Sometimes

**Network topology mattered:**

```
Home Network (working):
  ISP → IPv6 route exists → Connects via IPv6 ✓

Corporate Network (broken):
  ISP → IPv6 route → Corporate Firewall (BLOCKS IPv6) → Timeout ✗
  IPv4 fallback? → Not implemented in all clients → Still broken ✗
```

**Browser behavior varied:**
- Modern browsers: Happy Eyeballs (race both, use whichever works)
- Older browsers: Try IPv6, wait for timeout, maybe try IPv4
- Some tools: Hard-coded IPv6 preference, never fallback

---

## Questions

1. **Why did some clients fail to fallback to IPv4?**

2. **What is Happy Eyeballs and how does it prevent this?**

3. **Why did the PTR record mismatch cause issues?**

4. **How do you test IPv6 connectivity before deploying?**

5. **As a Senior Engineer, how do you design for dual-stack reliability?**

---

**When you've thought about it, read `step-01.md`**
