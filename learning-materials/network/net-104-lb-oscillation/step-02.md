# Step 2: Solutions

---

## Solution 1: Separate Health Endpoint

```go
// Health check should be lightweight
// Don't depend on external services
func HealthHandler(w http.ResponseWriter, r *http.Request) {
    // Just check if server is alive
    // Don't check database, cache, etc.
    w.WriteHeader(http.StatusOK)
}

// Readiness checks dependencies
func ReadinessHandler(w http.ResponseWriter, r *http.Request) {
    if db.Ping() != nil || !cache.IsReady() {
        w.WriteHeader(http.StatusServiceUnavailable)
        return
    }
    w.WriteHeader(http.StatusOK)
}
```

---

## Solution 2: Hysteresis

```yaml
# Different thresholds for up/down
healthCheck:
  healthyThreshold: 3    # 3 consecutive passes to mark healthy
  unhealthyThreshold: 5  # 5 consecutive failures to mark unhealthy
  timeout: 5s            # More generous timeout
```

---

## Solution 3: Dedicated Health Server

```go
// Separate server for health checks
// Different goroutine pool
// Different timeout handling
func healthServer() {
    mux := http.NewServeMux()
    mux.HandleFunc("/health", healthHandler)

    server := &http.Server{
        Addr:         ":8081",
        Handler:      mux,
        ReadTimeout:  1 * time.Second,
        WriteTimeout: 1 * time.Second,
    }
    server.ListenAndServe()
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's a separate health endpoint? (Lightweight /health that doesn't depend on external services)
2. What's the difference between health and readiness? (Health = alive, readiness = can serve traffic with dependencies)
3. What's hysteresis? (Different thresholds for up/down, requires multiple consecutive passes/failures)
4. What's a dedicated health server? (Separate HTTP server on different port with own resources)
5. Which solution is best? (Separate health endpoint + hysteresis + dedicated health server)

---

**Read `solution.md`
