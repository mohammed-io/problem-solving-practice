# Step 1: DNS Caching

---

## TTL Recommendations

```
Production services:
  - Low TTL before change: 60-300 seconds
  - Normal TTL: 300-3600 seconds
  - High traffic: 60 seconds (allows quick changes)

Static IPs:
  - TTL: 86400 seconds (24 hours)
  - Rarely changes, maximize caching

DNS during migration:
  - Lower TTL to 60 seconds 24 hours before
  - Make change
  - Raise TTL back after 2x propagation time
```

---

## Migration Strategy

```
Proper migration:

1. Day -1: Lower TTL to 60 seconds
2. Day 0: Update DNS to new IP (keep old IP too!)
3. Day 0: Keep old servers running
4. Day 1: Monitor traffic shift
5. Day 2: Shut down old servers
6. Day 3: Raise TTL to normal
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's DNS TTL? (Time-to-live - how long DNS records are cached)
2. What's the recommended TTL for production services? (60-3600 seconds, lower during changes)
3. What's the recommended TTL for static IPs? (86400 seconds - 24 hours)
4. What's the proper migration strategy? (Lower TTL 24h before, keep old servers running, raise after)
5. Why lower TTL before DNS changes? (Ensures caches expire quickly so new IP propagates)

---

**Read `step-02.md`**
