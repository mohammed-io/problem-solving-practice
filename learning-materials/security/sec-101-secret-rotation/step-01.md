# Step 1: Connection Pool Problem

---

## Why Rotation Failed

```
App Instance 1          App Instance 2          Database
     │                       │                      │
     │──conn(old pass)───────→│                      │
     │                       │──conn(old pass)─────→│
     │                       │                      │
     │ ←─still works─────────│ ←─still works──────│
     │                       │                      │
Rotation happens...
     │                       │                      │
     │──conn(new pass)───────X REJECTED!           │
     │                       │──conn(new pass)────X│
     │                       │                      │

Old connections still work, new ones fail!
```

**Connection pool behavior:**
```
Most pools:
- Keep connections open for reuse
- Don't check validity before use
- Only create new connections when needed
- New connections use NEW password from config
- Old connections (cached) use OLD password
```

---

## Zero-Downtime Rotation Strategy

**Two-phase commit:**

```
Phase 1: Database accepts BOTH passwords
Phase 2: Rotate all applications
Phase 3: Database accepts only NEW password
```

---

## Quick Check

Before moving on, make sure you understand:

1. Why did secret rotation fail? (Connection pools kept old connections with old password; new connections used new password and were rejected)
2. What's the connection pool problem? (Pools cache connections; new connections use new config but old ones persist)
3. What's two-phase rotation? (Phase 1: DB accepts both passwords; Phase 2: Rotate apps; Phase 3: DB accepts only new password)
4. Why can't we just rotate all apps simultaneously? (Impossible to guarantee, rolling deployments mean some apps always use old password during transition)
5. What's the core issue? (Database rejects new password while old connections still work with old password)

---

**Read `step-02.md`**
