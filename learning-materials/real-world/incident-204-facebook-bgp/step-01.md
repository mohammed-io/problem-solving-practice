# Step 1: BGP Withdrawal and the DNS Death Spiral

---

## How BGP Withdrawal Works

**Normal state - Facebook reachable:**

```
Router A (Verizon) BGP Table:
Destination     Next Hop        AS Path
1.1.1.0/24      → PeerRouter    [32934]        ← Can reach Cloudflare DNS
31.13.0.0/16    → PeerRouter    [32934]        ← Can reach Facebook
179.60.0.0/16   → PeerRouter    [32934]        ← Can reach Instagram

User tries: https://facebook.com
1. DNS query: facebook.com → 31.13.75.17
2. TCP connection: SYN to 31.13.75.17
3. Route found: via AS32934
4. Connection succeeds ✓
```

**After BGP withdrawal - Facebook gone:**

```
Router A (Verizon) BGP Table:
Destination     Next Hop        AS Path
1.1.1.0/24      → (no route)    [withdrawn]    ← Gone!
31.13.0.0/16    → (no route)    [withdrawn]    ← Gone!
179.60.0.0/16   → (no route)    [withdrawn]    ← Gone!

User tries: https://facebook.com
1. DNS query: facebook.com → ???
   - DNS servers at 1.1.1.1 (Cloudflare) still work
   - BUT facebook.com's authoritative DNS (a.ns.facebook.com) is unreachable!
   - a.ns.facebook.com → 31.13.75.17 → withdrawn → NO ROUTE

2. DNS query times out

3. Connection fails ✗
```

**The cascade:**

```
T+0s:     BGP withdrawal sent worldwide
T+30s:    Most ISPs process withdrawal
T+60s:    Facebook prefixes removed from global routing table
T+90s:    DNS queries for facebook.com start failing (cannot reach auth DNS)
T+120s:   User DNS caches expire, everyone gets SERVFAIL
T+180s:   All Facebook apps (Instagram, WhatsApp) show "no connection"
```

---

## The Circular Dependency

**Facebook's infrastructure dependency:**

```
                   ┌─────────────────────────────────────┐
                   │                                     │
                   │         facebook.com DNS             │
                   │      (a.ns.facebook.com, b.ns...)    │
                   │                                     │
                   └──────────────┬──────────────────────┘
                                  │
                    Hosted on Facebook's own network
                   (AS32934, IP addresses in withdrawn prefixes)
                                  │
                   ┌──────────────┴──────────────────────┐
                   │                                     │
                   ▼                                     ▼
          ┌─────────────────┐                 ┌─────────────────┐
          │  All Facebook   │                 │  Employee VPN   │
          │  services       │                 │  (vpn.fb.com)   │
          │  use facebook   │◄────────────────┤  needs DNS to  │
          │  .com domain    │                 │  find VPN IP    │
          └─────────────────┘                 └─────────────────┘
                   │                                     │
                   │                                     │
                   └─────────────┬───────────────────────┘
                                 │
                Everything breaks if facebook.com DNS unreachable
```

**What should have existed:**

```
1. Out-of-band DNS (different domain, different provider)
   Example: fb-dns.net hosted on Cloudflare/AWS

2. Out-of-band access (different network path)
   Example: Dedicated circuit, secondary ISP, console servers

3. VPN endpoint IP (not DNS)
   Example: vpn.facebook.com → 1.2.3.4 (hardcoded in VPN client)

4. Emergency contact process
   Example: Phone tree for physical access to data centers
```

---

## The BGP Configuration Problem

**What the tool did wrong:**

```go
package main

// Simplified version of what happened
type BGPConfigTool struct {
    routers []Router
    target  *string  // Will be set by --target flag
}

func (t *BGPConfigTool) UpdatePrefixes(prefixesFile string) error {
    prefixes := t.readPrefixes(prefixesFile)

    // BUG: Target validation was broken
    var targetRouters []Router
    if t.target == nil {
        // Should default to ONE router or REQUIRE target
        // Instead, it fell through to ALL routers
        targetRouters = t.routers
    } else {
        targetRouters = []Router{t.getRouter(*t.target)}
    }

    // BUG: Empty prefix list not validated
    if len(prefixes) == 0 {
        // Should have ERROR'd here
        log.Warn("Empty prefix list, proceeding anyway")
    }

    // Generate config that WITHDRAWS all routes
    for _, router := range targetRouters {
        config := t.generateBGPConfig(router, prefixes)
        t.pushConfig(router, config)
    }

    return nil
}

func (t *BGPConfigTool) GenerateBGPConfig(router Router, prefixes []string) string {
    if len(prefixes) == 0 {
        // This generates config that ANNOUNCES NOTHING
        // Equivalent to withdrawing all existing routes
        return `
router bgp 32934
 no network 1.1.1.0/24
 no network 31.13.0.0/16
 no network 179.60.0.0/16
 ...
`
    }
    // Normal config generation
    return t.generateNormalConfig(router, prefixes)
}
```

---

## The Recovery Process

**How they eventually fixed it:**

```
1. Physical access to data center (California)
   - Badge system offline
   - Security had emergency override procedure

2. Console cable to border router
   - Direct serial connection
   - No network needed

3. View configuration
   - Saw "no network" statements
   - Realized the problem

4. Manually restore BGP configuration
   - But had no valid backup easily accessible
   - Had to reconstruct from memory/docs

5. Restart BGP process
   - Routes announced again
   - Wait for global propagation (BGP convergence)

6. Verify connectivity
   - DNS servers reachable
   - Services coming back online

Total time: ~6 hours
```

---

## What Should Have Happened

**Safe deployment pattern:**

```go
package main

import (
    "fmt"
    "time"
)

type SafeBGPConfigTool struct {
    approvalRequired bool
}

func (t *SafeBGPConfigTool) UpdatePrefixes(target string, prefixesFile string, dryRun bool) error {
    // Step 1: Validate inputs
    if target == "" {
        return fmt.Errorf("target router REQUIRED")
    }

    router := t.getRouter(target)
    if router.IsCritical && !t.getApproval() {
        return fmt.Errorf("critical router requires approval")
    }

    prefixes := t.readPrefixes(prefixesFile)
    if len(prefixes) == 0 {
        return fmt.Errorf("prefix list cannot be empty")
    }

    // Step 2: Dry run first
    config := t.generateBGPConfig(router, prefixes)
    if dryRun {
        fmt.Println("Dry run. Config to be applied:")
        fmt.Println(config)
        fmt.Printf("\nRouter: %s\n", router.Hostname)
        fmt.Printf("Prefixes: %v\n", prefixes)

        var response string
        fmt.Printf("Apply to %s? (yes/no): ", router.Hostname)
        fmt.Scanln(&response)
        if response != "yes" {
            fmt.Println("Aborted")
            return nil
        }
    }

    // Step 3: Backup current config
    backup := t.backupConfig(router)
    fmt.Printf("Config backed up to: %s\n", backup)

    // Step 4: Apply to SINGLE router
    t.pushConfig(router, config)

    // Step 5: Verify BGP sessions
    time.Sleep(30 * time.Second) // Wait for BGP convergence
    if !t.verifyBGP(router) {
        fmt.Println("ERROR: BGP verification failed!")
        t.restoreConfig(router, backup)
        return fmt.Errorf("BGP verification failed")
    }

    // Step 6: Verify routes are being announced
    if !t.verifyAnnouncements(router) {
        fmt.Println("ERROR: Route announcements missing!")
        t.restoreConfig(router, backup)
        return fmt.Errorf("route announcements missing")
    }

    fmt.Printf("Successfully updated %s\n", router.Hostname)
    return nil
}

func (t *SafeBGPConfigTool) getApproval() bool {
    // Require explicit approval for critical routers
    var response string
    fmt.Print("Critical router! Type APPROVE to continue: ")
    fmt.Scanln(&response)
    return response == "APPROVE"
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's a BGP withdrawal? (Router announces it no longer has a route to a prefix, effectively removing it from global routing table)
2. Why did the circular dependency cause total failure? (DNS for facebook.com was hosted on Facebook's own network, which became unreachable after BGP withdrawal)
3. What's out-of-band management? (Separate network path for emergency access, independent of primary infrastructure)
4. Why did the BGP tool affect all routers? (Empty prefix list bug + missing target validation caused config to push to all routers)
5. What's the recovery process for BGP withdrawal? (Physical access, console cable, manual config restoration, wait for BGP convergence)

---

**Continue to `step-02.md`**
