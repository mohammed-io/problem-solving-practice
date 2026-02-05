# Step 1: The DNS Caching Problem

---

## DNS Resolution Flow

```
App Server: "Where is db-0.primary.github.net?"
→ Local DNS cache: "10.0.0.1 (TTL: 300s, cached at 20:00)"
→ Returns 10.0.0.1

App Server connects to 10.0.0.1...
→ But: 10.0.0.1 is no longer primary!
→ Connection refused.
```

**App server never re-queries DNS** because it uses cached value for full TTL.

---

## Why GitHub's Failover Broke Things

**Normal operation:**
```
Primary fails → HAProxy detects → Updates backend → App connections work
```

**What happened:**
```
Primary IP changed: 10.0.0.1 → 10.0.0.10
→ HAProxy config updated: ✓
→ DNS updated: db-0.primary.github.net → 10.0.0.10 ✓

→ But: App servers have cached DNS = 10.0.0.1
→ And: Connection pool maintains connections to cached IP
→ And: App never invalidates DNS cache!

→ Result: App still tries 10.0.0.1 → Refused
```

---

## Connection Pool Problem

```go
// Application code
var dbPool *sql.DB  // Global, initialized at startup

// Pool created at app startup
dbPool = sql.Open("mysql", "user@10.0.0.1:3306/db")

// After failover, pool still points to 10.0.0.1!
// App doesn't know to reinitialize pool
```

**Even if app re-queried DNS,** connection pool is already established.

---

## Quick Check

Before moving on, make sure you understand:

1. What's the DNS caching problem? (App servers cache DNS for full TTL, don't see IP changes)
2. Why did GitHub's failover break? (DNS updated but apps cached old IP, connection pool maintained stale connections)
3. Why is DNS a bad coordination mechanism? (Caching prevents immediate propagation, apps may not refresh)
4. What's the connection pool problem? (Pool created at startup with cached IP, not invalidated after failover)
5. Why did connections fail? (App connected to old primary IP which was now unavailable)

---

**Continue to `step-02.md`
