---
name: incident-204-facebook-bgp
description: System design problem
difficulty: Advanced
category: Real-World / Networking / BGP / Automation
level: Principal Engineer
---
# Real-World 204: Facebook BGP Blackout

---

## Tools & Prerequisites

To debug BGP routing issues:

### BGP Analysis Tools

| Tool | Purpose | Quick Usage |
|------|---------|-------------|
| **bgpq3** | BGP query tool | `bgpq3 -b AS32934` |
| **route-server** | Looking glass | `telnet route-server.ip 23` |
| **bgpstream** | BGP data stream | `bgpstream -w 3600` |
| **RIPEstat** | BGP stats API | `curl "https://stat.ripe.net/data/announced_prefixes/data.json?resource=AS32934"` |
| **bgp.he.net** | BGP looking glass | http://bgp.he.net |
| **bird/birdc** | BGP daemon CLI | `birdc show protocols` |
| **exabgp** | BGP injector/debugger | `exabgp --diagnose` |

### Key Commands

```bash
# Check if AS is announcing routes
whois -h whois.radb.net AS32934

# Query specific prefix from route collector
bgpview.net AS32934

# Check BGP route from multiple looking glasses
for lg in route-views.oregon-ix.net route-server.coppell.ipv6.he.net; do
  telnet $lg 23
done

# Check route propagation
curl "https://stat.ripe.net/data/routing-status/data.json?resource=1.1.1.0/24"

# View BGP updates in real-time
bgpstream -w 60 -c origin-as 32934

# Check local BGP status
birdc show protocols all
vtysh -c "show ip bgp summary"

# Check what prefixes are announced
birdc show route all protocol bgp
vtysh -c "show ip bgp"

# Simulate BGP withdrawal
exabgp --diagnose -- once 'announce 1.1.1.0/24 next-hop 192.168.1.1'

# Trace BGP path
traceroute -A AS32934 facebook.com

# Check BGP community values
whois -h whois.radb.net 1.1.1.0/24 | grep "origin:"

# Monitor BGP updates
bgpmon -a AS32934

# Check for route leaks
python3 -m pybgpstream -w 3600 | grep "AS32934"

# View route server information
whois -h whois.radb.net AS174

# Check prefix advertisement status
https://stat.ripe.net/data/announced-prefixes/data.json?resource=AS32934

# Check RPKI validation
curl "https://stat.ripe.net/data/rpki-validation/data.json?resource=1.1.1.0/24"

# View BGP communities
birdc show route where community = [32934];
```

### Key Concepts

**BGP (Border Gateway Protocol)**: Protocol that makes internet routing work; exchanges routing information between autonomous systems.

**AS Number (ASN)**: Autonomous System Number - unique identifier for a network (e.g., Facebook = AS32934).

**BGP Update**: Message announcing a route (prefix) to the internet.

**BGP Withdrawal**: Message announcing that a route is no longer available.

**Prefix**: IP address block announced via BGP (e.g., 1.1.1.0/24).

**Peering**: Direct connection between networks at Internet Exchange Points (IXPs).

**Transit**: Paying an ISP to carry your traffic to other networks.

**Border Router**: Router at edge of network that connects to other networks via BGP.

**BGP Session**: TCP connection (port 179) between BGP speakers exchanging routes.

**Route Reflection**: Method of distributing routes within an AS to avoid full mesh.

**BGP Community**: Tag attached to routes for signaling policies between networks.

**Looking Glass**: Server that allows viewing BGP routes from another network's perspective.

**Route Collector**: Server that collects and stores BGP tables from multiple networks for analysis.

**RPKI (Resource Public Key Infrastructure)**: Cryptographic method to validate BGP route announcements.

**BGP Hijack**: Announcing someone else's prefix illegitimately; causes traffic diversion.

**Route Leak**: Announcing routes through inappropriate paths, violating policies.

**IGP (Interior Gateway Protocol)**: Routing protocol within an AS (OSPF, IS-IS); distinct from BGP which is EGP.

---

## The Situation

You're a Principal Network Engineer at Meta (Facebook). Your network operates at massive scale:

``
Facebook AS Number: AS32934
Prefixes announced: 100+ (including 1.1.1.0/24 for Cloudflare DNS)
Border routers: 50+ edge locations worldwide
Peering relationships: 1000+ ISPs and IXPs
```

**Automation stack:**

```python
# Facebook's internal BGP automation (simplified)
class BGPConfigManager:
    def update_prefix_list(self, router: str, prefixes: list):
        """Push new prefix list to border router."""
        config = self.generate_config(prefixes)
        self.push_config(router, config)
        self.verify_bgp_sessions(router)

    def generate_config(self, prefixes: list) -> str:
        """Generate router configuration."""
        return f"""
router bgp 32934
 bgp router-id 1.2.3.4
 !
 ip prefix-list FACEBOOK-PREFIXES seq 5 permit {prefixes[0]}
 ip prefix-list FACEBOOK-PREFIXES seq 10 permit {prefixes[1]}
 ...
"""
```

---

## The Incident

```
Date: October 4, 2021
Duration: ~6 hours
Impact: Facebook, Instagram, WhatsApp, Messenger completely inaccessible
Also affected: Facebook employees' badge access, internal tools

Timeline (from public postmortem):
15:40 UTC - Engineer runs command to update BGP configuration
15:41 UTC - Command executed: push to all border routers
15:42 UTC - Border routers start withdrawing all Facebook routes
15:43 UTC - Facebook's DNS servers become unreachable
15:43 UTC -全世界 cannot resolve facebook.com
15:44 UTC - Engineers cannot access internal tools (they use facebook.com DNS!)
15:45 UTC - Cannot access router consoles (VPN requires facebook.com!)
16:00 UTC - Confusion: no one can access anything
21:00 UTC - Engineers physically access data center, restore config
21:50 UTC - Service slowly returning
```

---

## The Root Cause

**The command that caused it all:**

```bash
# Intended: Update prefix list for ONE border router
# Actual: Applied to ALL border routers with WRONG configuration

# The tooling error:
$ bgp-tool update-prefixes --target edge-router-123 \
    --file new_prefixes.txt

# But the tool had a bug:
# --target parameter was ignored, applied to ALL routers
# AND new_prefixes.txt had EMPTY prefix list!

# Result: All border routers configured to ANNOUNCE NOTHING
```

**What happened in BGP terms:**

```
Before (normal):
AS32934 announces: [1.1.1.0/24, 31.13.0.0/16, 179.60.0.0/16, ...]
→ Internet: "I can reach Facebook via AS32934"

After (incident):
AS32934 announces: [] (nothing!)
→ Internet: "I cannot reach AS32934, they have no routes"
→ All Facebook prefixes withdrawn from global routing table
→ Facebook effectively disappears from internet

Catch-22:
→ DNS servers (facebook.com) are hosted on Facebook's own network
→ Cannot resolve facebook.com because Facebook network is unreachable
→ Cannot VPN to Facebook network because DNS resolution fails
→ Cannot access router consoles because VPN requires facebook.com
```

---

## The Jargon

| Term | Definition | Analogy |
|------|------------|---------|
| **BGP Update** | Message announcing or withdrawing routes | Publishing or removing phone number from directory |
| **BGP Withdrawal** | Saying "I no longer have this route" | "I've moved, don't call this number" |
| **Prefix** | IP address block (like /24, /16) | Area code + exchange |
| **AS Number** | Autonomous System Number (network identifier) | Country code |
| **Border Router** | Router connecting to external networks | International airport |
| **Peering** | Direct connection between networks at IXP | Private road between two properties |
| **Transit** | Paying ISP to carry your traffic | Paying toll road operator |
| **Default Route** | "Send everything else here" (0.0.0.0/0) | "All other destinations go to gateway" |
| **BGP Session** | TCP connection between BGP speakers | Phone call between network administrators |
| **Route Reflection** | Distributing routes within an AS | Corporate memo distribution |

---

## The Design Failures

**1. Single command could affect all edge routers:**

```python
# NO STAGING, NO ROLLBACK
def push_to_production():
    # This went to ALL routers simultaneously
    for router in ALL_BORDER_ROUTERS:
        apply_config(router)
```

**2. DNS dependency loop:**

```
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│   facebook.com DNS ──hosted on──► Facebook network (AS32934)  │
│        ▲                                                     │
│        │                                                     │
│   Need to reach Facebook to... resolve facebook.com           │
│                                                                │
└────────────────────────────────────────────────────────────────┘

Circular dependency: Cannot resolve facebook.com without Facebook!
```

**3. Out-of-band access required but unavailable:**

```
Normal access: VPN → facebook.com → routers
VPN uses facebook.com DNS → fails when Facebook offline

Physical access: Drive to data center → plug console cable
But all data centers use badge access → badge system uses facebook.com DNS!
```

**4. No config validation before push:**

```python
# Empty prefix list SHOULD have been caught
prefixes = []  # Bug: file was empty or misread
if len(prefixes) == 0:
    # SHOULD have validation here
    pass  # No check! Proceeded with empty list
```

---

## Questions

1. **Why did removing all BGP routes make Facebook completely inaccessible?**

2. **What design flaw created the DNS dependency loop?**

3. **How should BGP changes be rolled out safely?**

4. **What out-of-band access should exist for emergencies?**

5. **As a Principal Engineer, how do you design network automation to prevent this?**

---

**When you've thought about it, read `step-01.md`**
