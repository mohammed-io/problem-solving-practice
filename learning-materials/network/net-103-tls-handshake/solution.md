# Solution: TLS Optimization

---

## Root Cause

New TLS handshake per request added 30-40ms latency.

---

## Solution

**Connection reuse + HTTP/2:**

```go
transport := &http.Transport{
    MaxIdleConns:       100,
    MaxIdleConnsPerHost: 100,
    IdleConnTimeout:    90 * time.Second,
    TLSClientConfig: &tls.Config{
        ClientSessionCache: tls.NewLRUClientSessionCache(128),
    },
    ForceAttemptHTTP2:  true,
}

// Single handshake, many requests
client := &http.Client{Transport: transport}
```

**Result:**
- First request: 40ms (handshake)
- Subsequent: 5ms (application only)

---

**Next Problem:** `network/net-104-lb-oscillation/`
