# Step 2: Out-of-Band Access and Circuit Breakers

---

## Out-of-Band Infrastructure

**The principle:** Have a separate, independent path for emergency access.

```
                    Normal Path (Failed during outage)
┌─────────────────────────────────────────────────────────────────┐
│  Laptop → VPN (vpn.fb.com) → Facebook Network → Internal Tools │
│                    ↓                                            │
│              DNS lookup (fb-dns)                               │
│              BUT: fb-dns hosted on Facebook network!           │
│              CIRCULAR DEPENDENCY                                │
└─────────────────────────────────────────────────────────────────┘

                    Emergency Path (Separate)
┌─────────────────────────────────────────────────────────────────┐
│  Laptop → VPN (hardcoded IP: 1.2.3.4) → Console Servers        │
│           │                                                     │
│           └─→ Uses different ISP (4G hotspot, home broadband)  │
│           └─→ Separate authentication (OTP + hardware token)   │
│           └─→ Direct serial console to routers                 │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```yaml
# Emergency access infrastructure
emergency_access:
  # Console servers with independent power and network
  console_servers:
    - location: "DC1-Santa-Clara"
      management_ip: "10.255.0.10/24"  # Separate management VLAN
      oob_ip: "198.51.100.10"          # Public IP for emergency access
      power: "UPS + Generator + Separate PDU"
      connection: "Serial console to all routers"

    - location: "DC2-Virginia"
      management_ip: "10.255.0.11/24"
      oob_ip: "198.51.100.11"

  # Emergency VPN (different from production)
  emergency_vpn:
    endpoint: "emergency-vpn.example.com"  # Different domain!
    endpoint_ip: "1.2.3.4"                  # Hardcoded IP in client
    auth:
      - hardware_key: "YubiKey"
      - otp: "Google Authenticator"
      - emergency_codes: "Printed codes in safe"
```

**Console server setup:**

```bash
#!/bin/bash
# setup_console_server.sh

# Console server provides out-of-band access to all routers
# Uses separate network path and authentication

# Install conserver (console server software)
apt-get install conserver

# Configure console connections to routers
cat > /etc/conserver/console.cf <<'EOF'
# Console server configuration
# Each router has a serial port connected to this server

console border-router-01 {
    master localhost;
    type unix;
    device /dev/ttyUSB0;
    baud 9600;
}

console border-router-02 {
    master localhost;
    type unix;
    device /dev/ttyUSB1;
    baud 9600;
}

console border-router-03 {
    master localhost;
    type unix;
    device /dev/ttyUSB2;
    baud 9600;
}

# Add all 50+ border routers...
EOF

# Start console server
systemctl enable conserver
systemctl start conserver

# Now you can access any router even if network is down:
# $ console border-router-01
```

---

## Circuit Breakers in Automation

**Pattern:** Prevent automated systems from taking dangerous actions.

```go
package main

import (
    "fmt"
    "time"
)

type SafetyLevel int

const (
    DryRun SafetyLevel = iota
    SingleNonCritical
    SingleWithApproval
    StagedRollout
    Emergency
)

type CircuitBreaker struct {
    blockedUntil  time.Time
    recentFailures []FailureRecord
    safetyLevel   SafetyLevel
}

type FailureRecord struct {
    Time    time.Time
    Type    string
    Reason  string
}

type Action struct {
    Type    string
    Target  *string
    Prefixes []string
    Force   bool
}

func (cb *CircuitBreaker) CheckActionAllowed(action Action) (bool, string) {
    // Check if circuit breaker is open
    if !cb.blockedUntil.IsZero() && time.Now().Before(cb.blockedUntil) {
        return false, fmt.Sprintf("Circuit breaker open until %s", cb.blockedUntil)
    }

    // Check for dangerous patterns
    if cb.isDangerousAction(action) {
        // Require explicit approval
        if !action.Force {
            return false, "Dangerous action requires force=true"
        }
    }

    // Check recent failures
    if cb.tooManyRecentFailures(action.Type) {
        return false, "Too many recent failures of this type"
    }

    return true, "OK"
}

func (cb *CircuitBreaker) isDangerousAction(action Action) bool {
    // Detect potentially dangerous actions
    if action.Type == "bgp_update" {
        // Empty prefix list (withdraws all routes)
        if len(action.Prefixes) == 0 {
            return true
        }
        // Affects all routers
        if action.Target == nil {
            return true
        }
    }

    return false
}

func (cb *CircuitBreaker) tooManyRecentFailures(actionType string) bool {
    cutoff := time.Now().Add(-1 * time.Hour)
    recent := 0
    for _, f := range cb.recentFailures {
        if f.Time.After(cutoff) && f.Type == actionType {
            recent++
        }
    }
    return recent >= 3
}

func (cb *CircuitBreaker) RecordFailure(action Action, reason string) {
    cb.recentFailures = append(cb.recentFailures, FailureRecord{
        Time:   time.Now(),
        Type:   action.Type,
        Reason: reason,
    })

    // Open circuit breaker if threshold reached
    if cb.tooManyRecentFailures(action.Type) {
        cb.blockedUntil = time.Now().Add(2 * time.Hour)
    }
}
```

---

## Staged Rollout Pattern

**Never change everything at once:**

```go
package main

import (
    "fmt"
    "math/rand"
    "time"
)

type StagedBGPDeployer struct {
    routers  []Router
    verifier BGPVerifier
}

func (d *StagedBGPDeployer) Deploy(config BGPConfig, percentage int) error {
    """
    Deploy to percentage of routers, verify, then continue.

    Args:
        config: BGP configuration to apply
        percentage: Percentage of routers to deploy to per stage
    """
    // Shuffle routers for random sampling
    routers := make([]Router, len(d.routers))
    copy(routers, d.routers)
    rand.Shuffle(len(routers), func(i, j int) {
        routers[i], routers[j] = routers[j], routers[i]
    })

    total := len(routers)
    batchSize := max(1, total*percentage/100)

    for i := 0; i < total; i += batchSize {
        end := min(i+batchSize, total)
        batch := routers[i:end]
        batchNum := i/batchSize + 1
        totalBatches := (total + batchSize - 1) / batchSize

        fmt.Printf("Deploying batch %d/%d (%d routers)\n", batchNum, totalBatches, len(batch))

        // Deploy to this batch
        for _, router := range batch {
            d.applyConfig(router, config)
        }

        // Wait for BGP convergence
        time.Sleep(60 * time.Second)

        // Verify each router
        var failed []string
        for _, router := range batch {
            if !d.verifier.Verify(router) {
                failed = append(failed, router.Hostname)
            }
        }

        if len(failed) > 0 {
            fmt.Printf("ERROR: Verification failed for: %v\n", failed)
            fmt.Println("Rolling back...")
            d.rollback(batch)
            return fmt.Errorf("deployment failed at batch %d", batchNum)
        }

        // Check global routing table
        if !d.verifier.CheckGlobalRouting() {
            fmt.Println("ERROR: Global routing table check failed!")
            d.rollback(batch)
            return fmt.Errorf("global routing check failed")
        }

        fmt.Printf("Batch %d successful\n", batchNum)
    }

    fmt.Println("All batches deployed successfully")
    return nil
}

func (d *StagedBGPDeployer) applyConfig(router Router, config BGPConfig) {
    router.ApplyConfig(config)
}

func (d *StagedBGPDeployer) rollback(routers []Router) {
    for _, router := range routers {
        router.Rollback()
    }
}
```

---

## Configuration Validation

**Validate before applying:**

```go
package main

import (
    "fmt"
    "net"
)

type BGPConfig struct {
    Prefixes    []string
    ASPath      []string
    Communities []string
}

func (c *BGPConfig) Validate() ([]string, error) {
    """Validate BGP configuration."""
    var errors []string

    // Check 1: Prefix list not empty
    if len(c.Prefixes) == 0 {
        errors = append(errors, "Prefix list cannot be empty")
    }

    // Check 2: Valid CIDR notation
    for _, prefix := range c.Prefixes {
        _, _, err := net.ParseCIDR(prefix)
        if err != nil {
            errors = append(errors, fmt.Sprintf("Invalid prefix: %s", prefix))
        }
    }

    // Check 3: AS path is reasonable
    if len(c.ASPath) > 64 {
        errors = append(errors, "AS path too long (max 64)")
    }

    // Check 4: Community format
    for _, community := range c.Communities {
        if !c.validCommunity(community) {
            errors = append(errors, fmt.Sprintf("Invalid community: %s", community))
        }
    }

    // Check 5: Not withdrawing all prefixes
    if len(c.Prefixes) < 3 { // Facebook has 100+ prefixes
        errors = append(errors, fmt.Sprintf("Warning: Only %d prefixes, expected 100+", len(c.Prefixes)))
    }

    if len(errors) > 0 {
        return errors, fmt.Errorf("configuration validation failed")
    }
    return nil, nil
}

func (c *BGPConfig) validCommunity(community string) bool {
    // Check BGP community format (nnnnnnnn)
    parts := splitString(community, ':')
    if len(parts) != 2 {
        return false
    }
    return isNumeric(parts[0]) && isNumeric(parts[1])
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's out-of-band (OOB) management? (Separate network path for emergency access, independent of primary infrastructure)
2. Why is a console server important? (Provides serial console access to routers even when network is down)
3. What's a circuit breaker in automation? (Pattern that prevents dangerous actions when too many recent failures)
4. Why use staged rollout for BGP changes? (Deploy to subset of routers, verify, then continue; allows rollback if issues detected)
5. What's the VPN endpoint IP pattern? (Hardcode IP in VPN client so it works even when DNS is unavailable)

---

**Continue to `solution.md`**
