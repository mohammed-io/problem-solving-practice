# Step 2: NUMA Optimization

---

## Strategy 1: Process Isolation

```bash
# Pin process to single NUMA node
numactl --cpunodebind=0 --membind=0 ./app

# Or use cgroups
echo "0-15" > /sys/fs/cgroup/cpuset/myapp/cpuset.cpus
echo "0" > /sys/fs/cgroup/cpuset/myapp/cpuset.mems
```

---

## Strategy 2: Multiple Processes

```
Instead of 1 process with 32 goroutines:
  Process 1: 16 goroutines on Node 0
  Process 2: 16 goroutines on Node 1

Each process stays on local node
No cross-node memory access
```

---

## Strategy 3: Local Allocations

```go
// In Go, allocations happen on current thread's M
// If goroutine stays on same node, memory is local

// Pin goroutines to OS threads (rarely recommended)
runtime.LockOSThread()
defer runtime.UnlockOSThread()

// Better: design for sharding per NUMA node
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's process isolation? (Pin process to specific NUMA node using numactl or cgroups)
2. Why use multiple processes? (Each process stays on local node, avoids cross-node memory access)
3. What's LockOSThread? (Pins goroutine to OS thread, keeps execution on same CPU/node)
4. What's sharding per NUMA node? (Design where each NUMA node handles separate data partition)
5. Which strategy is best? (Multiple processes with sharding - most scalable)

---

**Read `solution.md`
