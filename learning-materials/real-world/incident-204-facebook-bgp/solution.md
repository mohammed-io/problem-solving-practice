# Solution: BGP Automation Safety

---

## Root Cause Analysis

**The failure chain:**
1. BGP automation tool ignored `--target` parameter (bug)
2. Empty prefix list file not validated (missing check)
3. Configuration pushed to ALL border routers simultaneously (no staging)
4. No dry-run or preview of changes (missing safety)
5. Circular dependency: DNS hosted on network it's supposed to serve (design flaw)
6. No out-of-band access to routers (operational failure)

**Result:** Facebook disappeared from the internet for 6 hours.

---

## Complete Solution

### 1. Out-of-Band Access Infrastructure

**Dedicated emergency access network:**

```yaml
# Emergency Access Infrastructure Design
emergency_infrastructure:
  # Separate domain (not facebook.com)
  emergency_dns:
    domain: "meta-emergency.com"
    provider: "Cloudflare"  # External provider
    records:
      vpn: "vpn.meta-emergency.com A 1.2.3.4"
      console: "console.meta-emergency.com A 1.2.3.5"

  # Console servers in each data center
  console_servers:
    - dc: "SCL1"
      hostname: "conserver-scl1.meta-emergency.com"
      management_network: "10.255.0.0/24"
      oob_network: "198.51.100.0/24"
      connections:
        - device: "border-router-scl1-01"
          port: "/dev/ttyUSB0"
          baud: 9600
        - device: "border-router-scl1-02"
          port: "/dev/ttyUSB1"

    - dc: "ASH1"
      hostname: "conserver-ash1.meta-emergency.com"
      management_network: "10.255.1.0/24"
      connections: [...]

  # Emergency VPN
  emergency_vpn:
    type: "WireGuard"
    endpoint: "1.2.3.4:51820"
    public_key: "..."

  # Authentication
  authentication:
    primary: "Hardware key (YubiKey)"
    secondary: "TOTP (Google Authenticator)"
    emergency: "Printed one-time codes in vault"

  # Power independence
  power:
    - "UPS"
    - "Generator"
    - "Separate PDU from production equipment"
```

**Console server implementation:**

```python
import asyncio
import asyncssh
from typing import Dict, List

class ConsoleServer:
    """Manages out-of-band console access to routers."""

    def __init__(self, config: dict):
        self.config = config
        self.connections: Dict[str, asyncssh.SSHClientConnection] = {}

    async def connect_to_router(self, router_name: str) -> asyncssh.SSHClientConnection:
        """Establish console connection to router."""
        router_info = self.config['routers'][router_name]

        # Connect via console server's management network
        conn = await asyncssh.connect(
            router_info['console_host'],
            username=router_info['username'],
            password=router_info['password'],
            known_hosts=None  # Emergency access, skip host verification
        )

        # Connect to serial port
        writer, reader, _ = await conn.open_session(
            term_type='ansi',
            environment={'TERM': 'xterm-256color'}
        )

        self.connections[router_name] = conn
        return conn

    async def send_command(self, router_name: str, command: str) -> str:
        """Send command to router via console."""
        conn = self.connections.get(router_name)
        if not conn:
            conn = await self.connect_to_router(router_name)

        writer, reader, _ = await conn.open_session()
        writer.write(command + '\n')
        writer.write_eof()

        output = await reader.read()
        return output.decode()

    async def verify_bgp(self, router_name: str) -> bool:
        """Verify BGP is healthy on router."""
        output = await self.send_command(
            router_name,
            'show bgp summary | include "BGP state"'
        )
        return 'Established' in output

# Emergency access procedure
async def emergency_procedure():
    """Emergency procedure when main network is down."""
    console = ConsoleServer(emergency_config)

    # 1. Connect via emergency VPN
    await console.connect_emergency_vpn()

    # 2. Access console server
    await console.connect_to_console_server('conserver-scl1')

    # 3. Connect to border router
    await console.connect_to_router('border-router-scl1-01')

    # 4. Check BGP status
    status = await console.send_command(
        'border-router-scl1-01',
        'show run | section router bgp'
    )

    print(f"BGP Config:\n{status}")

    # 5. Fix if needed
    # ...
```

### 2. Safe BGP Automation

**Multi-stage validation:**

```python
from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum
import hashlib
import json

class DeploymentStage(Enum):
    VALIDATION = "validation"
    DRY_RUN = "dry_run"
    SINGLE_ROUTER = "single"
    CANARY = "canary"
    BATCHED_ROLLOUT = "batched"
    COMPLETE = "complete"

@dataclass
class BGPChange:
    prefixes: List[str]
    target: Optional[str] = None
    force: bool = False
    dry_run: bool = True
    batch_percentage: int = 10

    def __post_init__(self):
        # Auto-dry-run unless force=True
        if not self.force:
            self.dry_run = True

class BGPAutomation:
    """Safe BGP automation with multiple safety layers."""

    def __init__(self):
        self.stage = DeploymentStage.VALIDATION
        self.circuit_breaker = CircuitBreaker()
        self.config_backup = ConfigBackup()

    async def deploy(self, change: BGPChange) -> dict:
        """Deploy BGP change through all safety stages."""
        result = {
            'stage': self.stage.value,
            'success': False,
            'errors': []
        }

        # Stage 1: Validation
        self.stage = DeploymentStage.VALIDATION
        valid, errors = self._validate_change(change)
        if not valid:
            result['errors'] = errors
            return result

        # Stage 2: Dry run (show what would happen)
        self.stage = DeploymentStage.DRY_RUN
        preview = self._preview_change(change)
        result['preview'] = preview

        if change.dry_run:
            result['dry_run'] = True
            return result

        # Stage 3: Single router test
        self.stage = DeploymentStage.SINGLE_ROUTER
        if not change.target:
            change.target = self._select_test_router()
            result['test_router'] = change.target

        success = await self._deploy_single_router(change)
        if not success:
            result['errors'] = ["Single router deployment failed"]
            return result

        # Stage 4: Verify single router
        if not await self._verify_router(change.target):
            await self._rollback_router(change.target)
            result['errors'] = ["Router verification failed"]
            return result

        # Stage 5: Canary batch
        self.stage = DeploymentStage.CANARY
        canary_routers = self._select_canary_routers(count=3)
        for router in canary_routers:
            change.target = router
            if not await self._deploy_single_router(change):
                await self._rollback_all(canary_routers)
                result['errors'] = [f"Canary failed on {router}"]
                return result

        # Stage 6: Verify global routing
        if not await self._verify_global_routing():
            await self._rollback_all(canary_routers)
            result['errors'] = ["Global routing check failed"]
            return result

        # Stage 7: Batched rollout
        self.stage = DeploymentStage.BATCHED_ROLLOUT
        all_routers = self._get_all_routers()
        remaining = [r for r in all_routers if r not in canary_routers]

        batch_size = max(1, len(remaining) * change.batch_percentage // 100)
        for i in range(0, len(remaining), batch_size):
            batch = remaining[i:i+batch_size]
            for router in batch:
                change.target = router
                if not await self._deploy_single_router(change):
                    await self._rollback_all(batch)
                    result['errors'] = [f"Batch failed at {router}"]
                    return result

            if not await self._verify_global_routing():
                await self._rollback_all(batch)
                result['errors'] = ["Global routing failed during rollout"]
                return result

        self.stage = DeploymentStage.COMPLETE
        result['success'] = True
        return result

    def _validate_change(self, change: BGPChange) -> Tuple[bool, List[str]]:
        """Validate BGP change."""
        errors = []

        # Check 1: Target required
        if not change.target:
            errors.append("Target router is REQUIRED")

        # Check 2: Prefix list not empty
        if not change.prefixes:
            errors.append("Prefix list cannot be empty (would withdraw all routes!)")

        # Check 3: Minimum prefix count for Facebook
        if len(change.prefixes) < 50:
            errors.append(f"Warning: Only {len(change.prefixes)} prefixes, Facebook has 100+")

        # Check 4: Validate CIDR notation
        import ipaddress
        for prefix in change.prefixes:
            try:
                ipaddress.ip_network(prefix)
            except ValueError:
                errors.append(f"Invalid CIDR: {prefix}")

        # Check 5: Circuit breaker
        allowed, reason = self.circuit_breaker.check_action_allowed({
            'type': 'bgp_update',
            'target': change.target,
            'prefixes': change.prefixes,
            'force': change.force
        })
        if not allowed:
            errors.append(f"Circuit breaker: {reason}")

        return len(errors) == 0, errors

    def _preview_change(self, change: BGPChange) -> dict:
        """Generate preview of what will change."""
        current = self._get_current_config(change.target)
        new = self._generate_config(change)

        diff = self._diff_configs(current, new)

        return {
            'router': change.target,
            'prefixes_added': diff['added'],
            'prefixes_removed': diff['removed'],
            'config_hash': hashlib.sha256(new.encode()).hexdigest()[:16]
        }

    async def _verify_global_routing(self) -> bool:
        """Verify routes are announced globally."""
        # Query route collectors
        collectors = ['route-views.routeviews.org', 'rrc00.ripe.net']

        for collector in collectors:
            # Check if our prefixes are visible
            result = await self._query_route_collector(collector, 'AS32934')
            if len(result) < 50:  # Should see 100+ prefixes
                return False

        return True
```

### 3. Remove DNS Circular Dependency

**Host DNS on separate infrastructure:**

```yaml
# DNS Architecture
dns_architecture:
  # Authoritative DNS on external provider
  primary_dns:
    provider: "Cloudflare"
    records:
      facebook.com:
        - type: "A"
          value: "31.13.75.17"
        - type: "AAAA"
          value: "2a03:2880:f11c:8083:face:b00c:0:25de"

      # NS records point to Cloudflare, NOT Facebook
      - type: "NS"
        value: "ns1.cloudflare.com"
      - type: "NS"
        value: "ns2.cloudflare.com"

  # Internal DNS for Facebook services
  internal_dns:
    domain: "facebook.internal"
    hosted_on: "AWS Route53"  # Separate from Facebook network

    records:
      api.facebook.internal:
        type: "A"
        value: "10.0.0.10"

      vpn.facebook.internal:
        type: "A"
        value: "10.255.0.1"
```

### 4. Monitoring and Alerting

**BGP health dashboard:**

```python
class BGPMonitor:
    """Real-time BGP monitoring."""

    def __init__(self):
        self.route_collectors = [
            'route-views.routeviews.org',
            'rrc00.ripe.net',
            'rrc10.ripe.net'
        ]

    async def check_announced_prefixes(self, asn: int) -> dict:
        """Check what prefixes are announced for AS."""
        results = {}

        for collector in self.route_collectors:
            prefixes = await self._query_collector(collector, asn)
            results[collector] = {
                'count': len(prefixes),
                'prefixes': prefixes
            }

        # Alert if count drops significantly
        counts = [r['count'] for r in results.values()]
        avg = sum(counts) / len(counts)

        if avg < 50:  # Facebook has 100+
            await self.send_alert({
                'severity': 'CRITICAL',
                'message': f'Only {avg} prefixes announced for AS{asn}',
                'expected': '100+',
                'actual': int(avg)
            })

        return results

    async def check_route_leaks(self, asn: int) -> list:
        """Check for unauthorized announcements of our prefixes."""
        alerts = []

        # Our known prefixes
        our_prefixes = await self._get_our_prefixes()

        for collector in self.route_collectors:
            # Get all ASes announcing our prefixes
            announcements = await self._get_announcements(collector, our_prefixes)

            for announcement in announcements:
                if announcement['asn'] != asn:
                    alerts.append({
                        'severity': 'CRITICAL',
                        'message': f'AS{announcement["asn"]} announcing our prefix {announcement["prefix"]}',
                        'prefix': announcement['prefix'],
                        'asn': announcement['asn'],
                        'as_path': announcement['as_path']
                    })

        return alerts
```

---

## Trade-offs

| Approach | Safety | Complexity | Speed of Deployment |
|----------|--------|------------|---------------------|
| **Manual changes** | Low (human error) | Low | Slow |
| **Staged automation** | High | Medium | Medium |
| **Full automation with CB** | Very High | High | Fast (when safe) |
| **External DNS** | Very High | Low | Fast |

**Recommendation:** External DNS + staged automation with circuit breakers.

---

## Real Incident: Facebook/Meta 2021

**What happened:**
- BGP automation tool bug pushed empty config to all routers
- All Facebook prefixes withdrawn from internet
- DNS hosted on Facebook network, so DNS unreachable
- No out-of-band access to routers
- 6-hour outage while teams physically accessed data center

**What changed:**
- Implemented out-of-band console servers
- DNS moved to external provider (Cloudflare)
- Enhanced BGP automation with validation and staging
- Emergency VPN with separate authentication
- Circuit breakers in automation
- Multiple authorization required for dangerous changes

**Postmortem quote:**
> "We had single points of failure everywhere: tooling, access, DNS. We needed redundancy at every layer."

---

## Prevention Checklist

**For BGP automation:**
- [ ] Out-of-band access (console servers, emergency VPN)
- [ ] External DNS hosting (separate from main network)
- [ ] Staged deployment (single → canary → batched → all)
- [ ] Configuration validation (prefix count, CIDR format)
- [ ] Circuit breakers (block on repeated failures)
- [ ] Dry-run mode (preview before apply)
- [ ] Rollback automation (undo changes if verification fails)
- [ ] Global routing verification (check route collectors)

**For emergency access:**
- [ ] Console servers in each data center
- [ ] Emergency VPN (separate from production)
- [ ] Hardcoded IPs (no DNS dependency)
- [ ] Multiple authentication factors
- [ ] Emergency contact procedures
- [ ] Physical access process (badge override)

---

**Next Problem:** `observability/obs-101-cardinality-explosion/`
