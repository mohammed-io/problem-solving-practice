# Solution: Audit Logging

---

## Solution

**Middleware for automatic logging:**

```go
func AuditMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        start := time.Now()

        // Wrap response writer to capture status
        ww := &responseWriter{ResponseWriter: w}

        next.ServeHTTP(ww, r)

        // Log after request completes
        audit.Log(&AuditEvent{
            Timestamp: start,
            EventType: r.URL.Path,
            Actor: getUserID(r),
            Action: r.Method,
            Target: r.URL.RawPath,
            Result: ww.Status,
            Duration: time.Since(start),
        })
    })
}
```

**Configuration:**
- Send logs to external SIEM (Splunk, Elastic)
- Use S3 Object Lock for immutability
- Hash chain for tamper detection
- Mask sensitive fields before logging

---

**Next Problem:** `security/sec-103-rate-limit-bypass/`
