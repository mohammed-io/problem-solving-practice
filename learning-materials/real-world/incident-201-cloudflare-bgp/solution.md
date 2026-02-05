# Solution: BGP Route Leak Prevention

---

## Root Cause Analysis

**The attack vector:**

```
1. Cloudflare announced routes to Backup-ISP without prepend
2. Backup-ISP had no outbound filtering (announced to upstream)
3. Backup-ISP removed Cloudflare's AS from path (made it look like their route)
4. Verizon preferred "customer route" (Backup-ISP) over "peer route" (Cloudflare)
5. No RPKI validation existed to catch invalid announcement
```

**Three defensive layers failed:**
1. **Outbound prepends** - Not applied to backup route
2. **Downstream filtering** - Backup-ISP announced learned routes
3. **RPKI validation** - No cryptographic validation

---

## Complete Solution

### 1. Proper BGP Configuration

**Defensive outbound announcements:**

```bash
! cloudflare-router.conf
router bgp 13335
 bgp log-neighbor-changes
 bgp graceful-restart
 bgp graceful-restart restart-time 120
 bgp graceful-restart stalepath-time 360

! ========== PRIMARY UPSTREAM ==========
neighbor 203.0.113.1 remote-as 174
neighbor 203.0.113.1 description "Primary-Tier1-ISP"
neighbor 203.0.113.1 password encrypted <encrypted-password>
neighbor 203.0.113.1 route-map PRIMARY-IN in
neighbor 203.0.113.1 route-map PRIMARY-OUT out
neighbor 203.0.113.1 send-community both
neighbor 203.0.113.1 soft-reconfiguration inbound

! ========== BACKUP UPSTREAM ==========
neighbor 198.51.100.1 remote-as 65001
neighbor 198.51.100.1 description "Backup-Regional-ISP"
neighbor 198.51.100.1 password encrypted <encrypted-password>
neighbor 198.51.100.1 route-map BACKUP-IN in
neighbor 198.51.100.1 route-map BACKUP-OUT out
neighbor 198.51.100.1 send-community both
neighbor 198.51.100.1 soft-reconfiguration inbound

! ========== ROUTE MAPS ==========

! Announce OUR prefixes with prepend on backup
route-map PRIMARY-OUT permit 10
 match ip address prefix-list CLOUDFLARE-PREFIXES
 set local-preference 200
 set community 13335:100 additive
 set as-path prepend 13335 13335  ; 2x prepend (moderate)

route-map BACKUP-OUT permit 10
 match ip address prefix-list CLOUDFLARE-PREFIXES
 set local-preference 50
 set community 13335:500 additive  ; Mark as low-priority
 set as-path prepend 13335 13335 13335 13335 13335  ; 5x prepend!
 set community no-export additive  ; Don't propagate beyond this AS

! Our prefixes (only announce these)
ip prefix-list CLOUDFLARE-PREFIXES permit 1.1.1.0/24
ip prefix-list CLOUDFLARE-PREFIXES permit 104.16.0.0/12
ip prefix-list CLOUDFLARE-PREFIXES permit 172.64.0.0/13
ip prefix-list CLOUDFLARE-PREFIXES deny any

! ========== INBOUND FILTERING ==========
! Only accept what we should from this peer
ip prefix-list FROM-PRIMARY permit 0.0.0.0/0 le 32  ; All routes
ip prefix-list FROM-PRIMARY deny any

route-map PRIMARY-IN permit 10
 match ip address prefix-list FROM-PRIMARY
 set local-preference 200

route-map BACKUP-IN permit 10
 match ip address prefix-list FROM-BACKUP
 set local-preference 50

ip prefix-list FROM-BACKUP permit 0.0.0.0/0 le 32
ip prefix-list FROM-BACKUP deny any

! Maximum prefix limit (prevent route leaks from affecting us)
neighbor 203.0.113.1 maximum-prefix 1000000 10 restart 60
neighbor 198.51.100.1 maximum-prefix 50000 10 restart 60
```

### 2. RPKI Implementation

**Create Route Origin Authorizations:**

```bash
#!/bin/bash
# create-roas.sh - Create ROA for all Cloudflare prefixes

# Cloudflare prefixes
PREFIXES=(
    "1.1.1.0/24"
    "104.16.0.0/12"
    "172.64.0.0/13"
    "162.159.0.0/16"
)

AS_NUMBER=13335

for prefix in "${PREFIXES[@]}"; do
    # Extract prefix length for max-length
    # Use prefix-length as max-length for specific prefixes
    # For aggregates, allow /24 max

    max_length=$(echo $prefix | cut -d'/' -f2)
    if [ "$max_length" -le 16 ]; then
        max_length=24  # Allow more specific for aggregates
    fi

    echo "Creating ROA: $prefix → AS$AS_NUMBER (max-len $max_length)"

    # Using Krill (open-source RPKI software)
    # Or use hosted service: Cloudflare RPKI, RIPE Hosted PKI
    krillcli roas add \
        --asn $AS_NUMBER \
        --prefix "$prefix" \
        --max-length $max_length
done

# Publish to repository
krillcli republish
```

**Router RPKI configuration:**

```bash
router bgp 13335
 ! Connect to RPKI validator (Routinator, FORT, OctoRPKI)
 bgp rpki server tcp 192.0.2.10 3323
 !
 ! Bestpath behavior
 bgp bestpath prefix-rpki-valid allow
 bgp bestpath prefix-rpki-invalid ignore  ; Drop invalid routes
 !
 ! Logging
 bgp log neighbor changes detailed
!
! Enable RPKI on each neighbor
neighbor 203.0.113.1 rpki disable
```

**RPKI validation states:**

| State | Meaning | Action |
|-------|---------|--------|
| **Valid** | ROA exists and matches announcement | Accept |
| **Invalid** | ROA exists but ASN doesn't match | **DROP** |
| **Unknown** | No ROA exists | Accept (for now) |

### 3. Real-Time BGP Monitoring

**BGP monitoring system:**

```python
import asyncio
import websockets
import json
from dataclasses import dataclass
from typing import Set, Dict, List

@dataclass
class RouteEvent:
    prefix: str
    as_path: List[int]
    origin_as: int
    peer_asn: int
    timestamp: float
    event_type: str  # announce, withdraw, path_change

class BGPMonitor:
    def __init__(self, my_asn: int, my_prefixes: Set[str]):
        self.my_asn = my_asn
        self.my_prefixes = my_prefixes
        self.authorized_asns: Set[int] = set()

    async def stream_bgp_updates(self):
        """Connect to BGPStream and monitor in real-time."""
        # BGPStream provides websocket of BGP updates
        uri = "wss://stream.bgpstream.com/v2/stream"

        async with websockets.connect(uri) as websocket:
            # Subscribe to our prefixes
            for prefix in self.my_prefixes:
                subscribe_msg = {
                    "type": "subscribe",
                    "filters": {
                        "prefix": prefix
                    }
                }
                await websocket.send(json.dumps(subscribe_msg))

            # Process updates
            async for message in websocket:
                data = json.loads(message)
                await self.process_bgp_update(data)

    async def process_bgp_update(self, data: dict):
        """Process a BGP update and alert on anomalies."""
        event = RouteEvent(
            prefix=data['prefix'],
            as_path=data['as_path'],
            origin_as=data['as_path'][-1],
            peer_asn=data['peer_asn'],
            timestamp=data['timestamp'],
            event_type=data['type']
        )

        # Check 1: Unauthorized AS announcing our prefix
        if event.prefix in self.my_prefixes:
            if event.origin_as != self.my_asn:
                await self.alert(
                    severity="CRITICAL",
                    message=f"AS {event.origin_as} announcing our prefix {event.prefix}",
                    event=event
                )

        # Check 2: AS path suddenly shortened (possible leak)
        # Store previous AS paths per prefix and detect changes
        prev_path = self.get_previous_path(event.prefix)
        if prev_path and len(event.as_path) < len(prev_path) - 2:
            await self.alert(
                severity="WARNING",
                message=f"AS path shortened for {event.prefix}: {len(prev_path)} → {len(event.as_path)}",
                event=event
            )

        # Check 3: Withdrawal we didn't initiate
        if event.event_type == 'withdraw':
            if not self.self_initiated_withdrawal(event):
                await self.alert(
                    severity="CRITICAL",
                    message f"Unexpected withdrawal of {event.prefix}",
                    event=event
                )

    async def alert(self, severity: str, message: str, event: RouteEvent):
        """Send alert to various channels."""
        alert_data = {
            "severity": severity,
            "message": message,
            "prefix": event.prefix,
            "as_path": event.as_path,
            "origin_as": event.origin_as,
            "timestamp": event.timestamp
        }

        # Send to PagerDuty
        await self.send_pagerduty(alert_data)

        # Send to Slack
        await self.send_slack(alert_data)

        # Log for analysis
        self.log_alert(alert_data)

    def get_previous_path(self, prefix: str) -> List[int]:
        """Retrieve cached previous AS path for this prefix."""
        return self.path_cache.get(prefix)

# Run monitor
async def main():
    cloudflare_asn = 13335
    cloudflare_prefixes = {
        "1.1.1.0/24",
        "104.16.0.0/12",
        "172.64.0.0/13"
    }

    monitor = BGPMonitor(cloudflare_asn, cloudflare_prefixes)
    await monitor.stream_bgp_updates()

if __name__ == "__main__":
    asyncio.run(main())
```

### 4. Route Server Configuration (For IXPs)

**If you're a route server operator:**

```bash
! Prevent route leaks at Internet Exchange

route-policy RS-CLIENT-IN
  ! Accept only customer's own prefixes
  if rib_has_route_prefix registered_to_client then
    pass
  else
    drop
  endif

route-policy RS-CLIENT-OUT
  ! Don't announce routes learned from one RS client to another
  if rib_has_route_prefix learned_from_rs_client then
    drop
  endif
  ! Add no-export community to prevent leaks
  set community no-export additive
  pass

! Apply to all route server clients
router bgp 64500
  neighbor 203.0.113.10 route-policy RS-CLIENT-IN in
  neighbor 203.0.113.10 route-policy RS-CLIENT-OUT out
```

---

## Trade-offs

| Defense | Effectiveness | Complexity | Overhead |
|---------|---------------|------------|----------|
| **AS Path Prepend** | Medium | Low | None |
| **Route Filtering** | High | Medium | Maintenance |
| **RPKI** | Very High | Medium | Setup + validation |
| **Real-time Monitoring** | Medium (detective) | High | Infrastructure |
| **BGP Communities** | Low (depends on others) | Low | None |

**Recommendation:** Implement all layers. RPKI + filtering + monitoring.

---

## Real Incident: Cloudflare 2021

**What happened:**
- Small ISP (conditionally) announced Cloudflare's routes upstream
- Verizon preferred "customer route" over direct peering
- No RPKI validation existed to drop invalid routes
- Traffic routed through ISP with insufficient capacity

**What changed:**
- Implemented RPKI for all prefixes
- Added aggressive prepends on backup routes
- Set up real-time BGP monitoring
- Added prefix-list filtering on all neighbor relationships

**Postmortem quote:**
> "BGP security is like backyard security: locks, cameras, and dogs. Layers, layers, layers."

---

## Quick Checklist

**Before announcing prefixes:**
- [ ] Created ROAs for all prefixes
- [ ] Configured aggressive prepends on backup/transit
- [ ] Added prefix-list filtering on all neighbors
- [ ] Set maximum-prefix limits
- [ ] Enabled MD5 passwords on all sessions
- [ ] Set up real-time BGP monitoring
- [ ] Documented all peer relationships
- [ ] Test failover scenarios

**Operational:**
- [ ] Monitor BGP feeds for anomalies
- [ ] Review route collector data weekly
- [ ] Update ROAs when adding prefixes
- [ ] Run quarterly BGP security audits
- [ ] Participate in MANRS initiative

---

**Next Problem:** `real-world/incident-202-stackoverflow-ipv6/`
