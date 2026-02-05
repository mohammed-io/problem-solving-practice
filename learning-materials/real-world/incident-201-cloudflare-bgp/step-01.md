# Step 1: BGP Path Selection and Route Leak Mechanics

---

## Why Verizon Chose the "Worse" Path

**Normal peering vs. transit relationship:**

```
          Peer Relationship ( settlement-free, equal )
                     │
    Verizon ──────────────── Cloudflare
        │                          ▲
        │                          │
        │        Customer Relationship (pays for service)
        │                          │
        └──────────→ Backup-ISP ───┘
```

**BGP prefers customer routes over peer routes!**

```
Priority (Local Preference):
1. Customer routes (local-pref: 100-200)  ← Backup-ISP announcement
2. Peer routes (local-pref: 50-100)      ← Direct peering
3. Transit routes (local-pref: 0-50)
```

**The leak:**

```
Step 1: Cloudflare announces to Backup-ISP
  → Prefix: 1.1.1.0/24
  → AS Path: [13335]  (Cloudflare's own AS)

Step 2: Backup-ISP SHOULD have:
  → Added to its own AS path: [65001, 13335]
  → NOT announced upstream (internal use only)

Step 3: Instead, Backup-ISP announced to Verizon:
  → Prefix: 1.1.1.0/24
  → AS Path: [65001]  ← Removed Cloudflare's AS!
  → Origin: IGP (like it's their own IP space!)

Step 4: Verizon sees:
  → Direct peer: AS path [13335], local-pref 100 (peer relationship)
  → Via Backup-ISP: AS path [65001], local-pref 200 (customer relationship!)

  → Verizon chooses Backup-ISP route (higher local-pref)
```

---

## AS Path Prepend Explained

**Making routes look less attractive:**

```bash
# No prepend (looks short, attractive)
route-map NO-PREPEND permit 10
  ! AS path: [65001, 13335]
  ! Competitors might prefer this!

# With prepend (looks long, unattractive)
route-map WITH-PREPEND permit 10
  set as-path prepend 65001 65001 65001
  ! AS path: [65001, 65001, 65001, 65001, 13335]
  ! ISPs prefer shorter paths!
```

**Visualizing prepend:**

```
No prepend:  Verizon ← Backup-ISP ← Cloudflare
              (2 ASes in path)

With prepend: Verizon ← Backup-ISP ← Backup-ISP ← Backup-ISP ← Cloudflare
              (5 ASes in path - looks much longer!)
```

---

## Route Filtering: The Safety Net

**What Backup-ISP SHOULD have done:**

```bash
# route-filter.conf
# Only announce OUR IP space to upstream
ip prefix-list OUR-PREFIXES permit 198.51.0.0/16 le 24
ip prefix-list OUR-PREFIXES deny any

# Apply to upstream neighbor
neighbor 203.0.113.1 route-filter OUR-PREFIXES out

# Result: Cloudflare's routes (1.1.1.0/24) blocked!
```

**Prefix lists:**

```bash
# Cloudflare's actual prefixes (for reference)
ip prefix-list CLOUDFLARE-PREFIXES seq 5 permit 1.1.1.0/24
ip prefix-list CLOUDFLARE-PREFIXES seq 10 permit 104.16.0.0/12
ip prefix-list CLOUDFLARE-PREFIXES seq 15 permit 172.64.0.0/13

# Block these from being announced to upstream!
ip prefix-list UPSTREAM-OUT deny 1.1.1.0/24
ip prefix-list UPSTREAM-OUT deny 104.16.0.0/12
ip prefix-list UPSTREAM-OUT deny 172.64.0.0/13
ip prefix-list UPSTREAM-OUT permit 198.51.0.0/16 le 24
```

---

## Quick Check

Before moving on, make sure you understand:

1. Why did Verizon choose the "worse" path? (BGP prefers customer routes over peer routes via local-pref)
2. What's a route leak? (ISP announces routes learned from one peer to other peers, leaking private routes)
3. What's AS path prepend? (Adding your own AS multiple times to make path look longer/less attractive)
4. What's local-pref? (BGP attribute where higher values are preferred, customer routes get highest)
5. What's prefix filtering? (Only announcing your own IP prefixes, blocking others from being leaked)

---

**Continue to `step-02.md`
