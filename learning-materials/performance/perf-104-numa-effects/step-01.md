# Step 1: Understanding NUMA

---

## NUMA Architecture

```
Single Socket (UMA):
[CPU0] [CPU1] [CPU2] [CPU3]
    │      │      │      │
    └──────┴──────┴──────┘
           │
        [RAM]
All CPUs access RAM at same speed

Dual Socket (NUMA):
Node 0              Node 1
[CPU0-7]           [CPU8-15]
    │                  │
  [RAM 0]           [RAM 1]
    │                  │
    └──── UPI ────────┘

Local access: fast
Remote access: slow (~1.5x)
```

---

## Detecting NUMA

```bash
# Check NUMA topology
lscpu | grep NUMA

# NUMA node(s): 2
# NUMA node0 CPU(s): 0-15
# NUMA node1 CPU(s): 16-31

# Check memory allocation
numastat
# Show memory allocation per node
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's NUMA? (Non-Uniform Memory Access - multi-socket systems where memory access speed depends on which CPU)
2. What's local vs remote memory access? (Local = same socket = fast, remote = other socket = ~1.5x slower)
3. What's UPI? (Ultra Path Interconnect - Intel's connection between CPU sockets)
4. How do you detect NUMA topology? (lscpu | grep NUMA, shows nodes and CPU assignments)
5. Why does NUMA matter? (Cross-node memory access is slower, can cause performance issues)

---

**Read `step-02.md`
