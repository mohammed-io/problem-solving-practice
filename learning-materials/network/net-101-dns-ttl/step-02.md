# Step 2: Beyond DNS

---

## Connection Pool Problem

```
Even with DNS TTL=60:
App connects at T=0, gets IP=A
DNS changes at T=60 to IP=B
App still uses IP=A (connections cached!)
Pool doesn't refresh until connection fails

Solution: Periodically close/reconnect
Or: Use TTL shorter than connection lifetime
```

---

## Tools for DNS Debugging

```bash
# Check current TTL
dig api.example.com
# Look for ";" in AUTHORITY SECTION

# Check specific DNS server
dig @8.8.8.8 api.example.com

# Flush local cache
sudo systemd-resolve --flush-caches  # Linux
sudo dscacheutil -flushcache          # Mac
ipconfig /flushdns                   # Windows

# Trace DNS path
dig +trace api.example.com
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's the connection pool problem? (Connections cache IP, don't refresh after DNS change)
2. How do you solve connection pool caching? (Periodically close/reconnect, or shorter TTL than connection lifetime)
3. What's `dig` used for? (DNS lookup and debugging)
4. What's `dig @8.8.8.8`? (Query specific DNS server instead of default)
5. How do you flush local DNS cache? (systemd-resolve --flush-caches, dscacheutil -flushcache, or ipconfig /flushdns)

---

**Read `solution.md`
