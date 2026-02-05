# Step 05: High Availability - Quorum and Multi-Region

---

## The Problem

The coordination service itself can fail. How do you keep it available?

```
Single etcd node:
❌ Node fails → ENTIRE SYSTEM DOWN
```

---

## Solution: Cluster with Quorum

etcd uses **Raft consensus** - needs majority (quorum) to operate.

```
3-node cluster:
┌─────────┐  ┌─────────┐  ┌─────────┐
│ etcd-1  │  │ etcd-2  │  │ etcd-3  │
└────┬────┘  └────┬────┘  └────┬────┘
     │            │            │
     └────────────┴────────────┘
                  │
            Quorum = 2 nodes (majority of 3)

┌─────────────────────────────────────────────────────────────┐
│  Failure scenarios:                                         │
│                                                             │
│  1 node fails:  2 nodes remain → quorum maintained ✓       │
│  2 nodes fail: 1 node remains → NO quorum ✗                │
│                                                             │
│  Writes require quorum (2 nodes to acknowledge)            │
│  Reads can be stale (for performance) or linearizable       │
└─────────────────────────────────────────────────────────────┘
```

---

## Choosing Cluster Size

| Cluster Size | Quorum | Tolerates | Recommended |
|--------------|--------|-----------|-------------|
| **1 node** | 1 | 0 failures | ❌ Dev only |
| **3 nodes** | 2 | 1 failure | ✅ Good for most |
| **5 nodes** | 3 | 2 failures | ✅ Production critical |
| **7 nodes** | 4 | 3 failures | ⚠️ Diminishing returns |

**Rule:** Always use odd numbers (avoids ties).

```
Why odd?

4 nodes: Quorum = 3
- If 2 nodes fail, 2 remain → NO quorum (2 is not majority of 4)
- Can only tolerate 1 failure

5 nodes: Quorum = 3
- If 2 nodes fail, 3 remain → quorum maintained
- Can tolerate 2 failures

5 nodes gives better fault tolerance than 4!
```

---

## Multi-Region Deployment

**Challenge:** etcd requires low latency (Raft is sensitive to network delays).

```
Option 1: Single-region etcd
┌─────────────────┐
│   Region: US-East  │
│                   │
│   etcd-1, etcd-2, etcd-3  │
└─────────────────┘
         │
         ▼
   Global services (read/write)
   ✅ Simple, fast
   ❌ US-East failure = global outage

Option 2: Multi-region etcd (complex)
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  US-East    │  │  EU-West    │  │  AP-South   │
│  etcd-1,2,3  │  │  etcd-4,5,6  │  │  etcd-7,8,9  │
└─────────────┘  └─────────────┘  └─────────────┘
      │                │                │
      └────────────────┴────────────────┘
                       ▼
              Raft consensus across regions
              ✅ Each region has local etcd
              ❌ High latency between regions
              ❌ Complex to operate

Option 3: Single-region + read replicas (recommended)
┌─────────────────┐
│   Region: US-East  │
│                   │
│   etcd-1,2,3 (writes)  │
│   etcd-4,5 (read replicas)  │
└─────────────────┘
         │
         ▼
   Global services (read/write)
   ✅ Writes go to primary etcd
   ✅ Reads can be local (eventual consistency)
   ⚠️ US-East failure = global outage (mitigate with cache)
```

---

## Deployment Topology

```yaml
# Production: 5 nodes across 3 AZs
etcd-cluster:
  nodes:
    - name: etcd-1
      zone: us-east-1a
    - name: etcd-2
      zone: us-east-1b
    - name: etcd-3
      zone: us-east-1c
    - name: etcd-4
      zone: us-east-1a  # same zone as etcd-1, but different host
    - name: etcd-5
      zone: us-east-1b  # same zone as etcd-2, but different host

# Quorum = 3
# Can lose 1 entire AZ (2 nodes) and still have quorum
```

---

## Quick Check

Before moving on, make sure you understand:

1. What is quorum? (Majority of nodes)
2. Why use odd cluster sizes? (Avoids ties, better fault tolerance)
3. What's the recommended cluster size? (3 or 5 nodes)
4. How do you deploy across regions? (Single-region + read replicas preferred)

---

**Ready to handle coordination service failures? Read `step-06.md`**
