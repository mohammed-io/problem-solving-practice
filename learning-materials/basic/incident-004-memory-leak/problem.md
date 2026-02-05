---
name: incident-004-memory-leak
description: Memory leak in payment service
difficulty: Basic
category: Incident Response
level: Mid-level
---
# Incident 004: Memory Leak - Node.js

---

## The Situation

You're on-call for the payment processing service. It's 3 AM when your pager goes off.

```
🚨 CRITICAL: payment-service memory usage > 90% for 5 minutes
```

---

## What You See

### Kubernetes Pod Status

```bash
$ kubectl get pods -l app=payment-service
NAME                              READY   STATUS    RESTARTS   AGE
payment-service-7d8f9c8d-abc12   0/1     OOMKilled 2          4h
payment-service-7d8f9c8d-xyz45   1/1     Running   0          4h
payment-service-7d8f9c8d-def78   0/1     OOMKilled 1          4h
payment-service-7d8f9c8d-ghi90   1/1     Running   0          4h
```

Notice: Some pods are `OOMKilled` - killed for using too much memory.

### Grafana Memory Graph

```
Memory Usage (GB)
6 ┤                              ╭────╮
5 ┤                         ╭────╯    ╰─────────╮
4 ┤                   ╭─────╯                   ╰────╮
3 ┤             ╭─────╯                               ╰───
2 ┤       ╭─────╯
1 ┤ ╭─────╯
0 └─┬─────┬─────┬─────┬─────┬─────┬─────┬─────
  00:00  01:00  02:00  03:00  04:00  05:00  06:00  07:00
              ↑Restart deployed at 02:00
```

Memory is **steadily increasing** after each restart.

### Container Limits

```yaml
resources:
  requests:
    memory: "512Mi"
  limits:
    memory: "1Gi"
```

Pods are killed when they hit 1GB (`OOMKilled`).

---

## Recent Changes

**Deployed 4 hours ago:** New fraud detection feature

```javascript
// NEW CODE - runs on every payment request
async function checkFraud(payment) {
  const riskyUsers = await redis.get('risky_users');

  if (!riskyUsers) {
    // Fetch from database
    const users = await db.query(
      'SELECT user_id FROM risky_users WHERE active = true'
    );
    const riskySet = new Set(users.rows.map(r => r.user_id));

    // Cache for 5 minutes
    await redis.setex('risky_users', 300, JSON.stringify([...riskySet]));

    return riskySet.has(payment.userId);
  }

  const riskySet = new Set(JSON.parse(riskyUsers));
  return riskySet.has(payment.userId);
}
```

This code runs **on every payment request** (roughly 100 requests/second).

---

## Jargon

| Term | Definition |
|------|------------|
| **OOMKilled** | Container terminated for exceeding its memory limit (Out Of Memory) |
| **Memory leak** | Memory allocated but never released, causing continuous growth |
| **Heap** | Region of memory used for dynamic allocation |
| **Garbage collection** | Automatic reclaiming of unused memory |
| **GC pressure** | How hard garbage collector has to work to free memory |
| **Closure** | Function that retains access to variables from its outer scope |
| **Event loop** | Node.js mechanism for handling async operations |

---

## Your Task

1. **What's the memory leak pattern here?** (Hint: What's being created repeatedly?)

2. **Why isn't garbage collection cleaning it up?**

3. **What's the fix?** (Multiple valid approaches)

4. **As a Staff Engineer, what monitoring would have caught this in staging?**

---

**When you've thought about it, read `solution.md`**
