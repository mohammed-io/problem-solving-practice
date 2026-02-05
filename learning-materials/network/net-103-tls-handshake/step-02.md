# Step 2: Optimization Strategies

---

## Strategy 1: Connection Reuse

```go
// HTTP/2: Single TCP connection, multiplexed requests
// HTTP/1.1: Keep-Alive, pool connections

transport := &http.Transport{
    TLSClientConfig: &tls.Config{
        // Enable session resumption
        ClientSessionCache: tls.NewLRUClientSessionCache(128),
    },
    MaxIdleConns:        100,   // Keep connections open
    MaxIdleConnsPerHost: 100,
    IdleConnTimeout:     90 * time.Second,
    ForceAttemptHTTP2:   true,  // Prefer HTTP/2
}
```

---

## Strategy 2: HTTP/2

```
HTTP/1.1: One request per connection (mostly)
HTTP/2: Many requests per connection

Benefit:
- Amortize TLS handshake over many requests
- Multiplexing without head-of-line blocking
- Better compression (HPACK)
```

---

## Strategy 3: Session Tickets

```go
tlsConfig := &tls.Config{
    ClientSessionCache: tls.NewLRUClientSessionCache(128),
    // Session tickets enable faster resumption
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's the benefit of HTTP/2 for TLS? (Amortizes handshake over multiplexed requests)
2. What's ClientSessionCache? (Cache for TLS session tickets, enables faster resumption)
3. What's connection pooling? (Reuse connections to avoid repeated handshakes)
4. What's HPACK? (HTTP/2 header compression)
5. What's the best optimization strategy? (Connection reuse + HTTP/2 + session tickets)

---

**Read `solution.md`
