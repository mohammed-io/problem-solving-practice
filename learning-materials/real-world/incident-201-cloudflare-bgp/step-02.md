# Step 2: Detection and Prevention

---

## Detecting BGP Leaks in Real-Time

### 1. Route Collectors

```python
import requests
from datetime import datetime

def check_bgp_routes(as_number, prefix):
    """
    Query RouteViews or RIPE RIS to see who's announcing your prefix.
    """
    # RIPE Stat API
    api_url = f"https://stat.ripe.net/data/announced-prefixes/data.json?resource={as_number}"

    response = requests.get(api_url)
    data = response.json()

    announced_prefixes = data['data']['announced_prefixes']

    alerts = []
    for announcement in announced_prefixes:
        if announcement['prefix'] == prefix:
            # Check who's announcing it
            announcers = announcement['announcing_asns']
            print(f"Prefix {prefix} announced by: {announcers}")

            # Alert if unknown AS is announcing our prefix
            for asn in announcers:
                if asn not in AUTHORIZED_ASNS:
                    alerts.append({
                        'severity': 'CRITICAL',
                        'message': f'Unauthorized ASN {asn} announcing {prefix}',
                        'timestamp': datetime.utcnow().isoformat()
                    })

    return alerts

# Authorized ASNs (your own + legitimate peers)
AUTHORIZED_ASNS = {13335, 174, 3356, 2914}  # Cloudflare + major peers

# Run check every minute
while True:
    alerts = check_bgp_routes(13335, '1.1.1.0/24')
    for alert in alerts:
        send_alert(alert)  # PagerDuty, Slack, etc
    time.sleep(60)
```

### 2. BGP Monitoring Tools

**Route Collector Servers:**
- RIPE RIS (Route Information Service)
- RouteViews (University of Oregon)
- BGPMon (real-time BGP analysis)

**What they do:**
- Peer with hundreds of ASes worldwide
- Collect all BGP announcements
- Provide query API and streaming feeds

### 3. RPKI (Resource Public Key Infrastructure)

**Cryptographic route validation:**

```bash
# Create ROA (Route Origin Authorization)
# This says: "Only AS 13335 can announce 1.1.1.0/24"

$ rsync rpki-client.ripe.net::repository/ .

# Create ROA object
$ roa-create \
  --asn 13335 \
  --prefix 1.1.1.0/24 \
  --max-length 24 \
  --output roa-1.1.1.0-24.roa

# Publish to repository
$ rsync roa-1.1.1.0-24.roa rpki-repository.ripe.net::repository/

# Now routers can validate!
# If Backup-ISP (AS 65001) announces 1.1.1.0/24:
# → Router: "ROA says only AS 13335 can announce this! DROP!"
```

**Router configuration with RPKI:**

```bash
# Enable RPKI validation
router bgp 13335
 bgp rpki server tcp 192.0.2.1 3323
 !
 ! Drop invalid routes
 bgp bestpath prefix-rpki-valid allow
 bgp bestpath prefix-rpki-invalid ignore
```

---

## Prevention: Defense in Depth

### Layer 1: Your Announcements (Outbound)

```bash
# Always prepend on backup/transit routes
route-map BACKUP-OUT permit 10
 set as-path prepend 13335 13335 13335 13335  ; 4x prepend
 set local-preference 50                      ; Low preference
 set community 13335:666  ; Mark for filtering
```

### Layer 2: Filter What You Accept (Inbound)

```bash
# Only accept prefixes you should receive from this peer
ip prefix-list FROM-PEER-X permit 203.0.113.0/24 le 32
ip prefix-list FROM-PEER-X deny any

neighbor 203.0.113.1 prefix-list FROM-PEER-X in
```

### Layer 3: Route Server Policies (For IXPs)

```bash
# "Don't announce what you learn from one peer to another"
route-map RS-CLIENT-OUT deny 10
  match ip address peer-as-routes
  ! Block routes learned from other RS clients

route-map RS-CLIENT-OUT permit 20
  set no-export
  ! Even if announced, don't propagate beyond this AS
```

### Layer 4: RPKI Validation

```
Create ROAs for all your prefixes
Enable RPKI validation on all edge routers
Configure: valid=accept, invalid=drop, unknown=evaluate
```

### Layer 5: Real-Time Monitoring

```
Run BGP stream monitoring (BGPStream, bgpstream.com)
Set alerts for:
- New AS announcing your prefixes
- AS path changes (sudden shortenings)
- Prefix length changes (1.1.1.0/24 → 1.1.1.0/25)
- Withdrawals that don't match your announcements
```

---

## BGP Communities for Control

**Tagging routes for downstream handling:**

```bash
# Well-known communities
route-map OUTBOUND permit 10
 set community no-export       ; "Don't announce beyond this AS"
 set community no-advertise    ; "Don't announce to anyone"
 set community local-as        ; "Don't announce outside my confederation"

# Custom communities (for your use)
route-map TO-BACKUP-ISP permit 10
 set community 13335:90  ; "Low priority route"
 set community 13335:backup  ; "This is backup, don't use as primary"

# Downstream can filter on these:
# (on Backup-ISP's router)
route-map TO-UPSTREAM deny 10
 match community 13335:backup  ; Don't announce backup routes upstream

route-map TO-UPSTREAM permit 20
 set community no-export
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's RPKI? (Resource Public Key Infrastructure - cryptographic route validation)
2. What's a ROA? (Route Origin Authorization - states which AS can announce a prefix)
3. What's a route collector? (Servers like RIPE RIS, RouteViews that collect BGP announcements)
4. What are BGP communities? (Tags attached to routes for filtering and policy control)
5. What's the prevention strategy? (RPKI + prefix filtering + AS path prepend + monitoring)

---

**Continue to `solution.md`**
