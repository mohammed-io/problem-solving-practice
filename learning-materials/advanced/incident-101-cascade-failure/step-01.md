# Step 1: Analyze the Retry Storm

---

## The Math of Retries

**Normal operation:**
```
1667 req/s to Service A
Each request: 50ms
Concurrent requests: 1667 × 0.05 = ~83
```

**During degradation (Service A slow):**
```
1667 req/s new
+ 1667 × 3 = 5001 req/s retries
= 6668 req/s total

Each request: 5000ms (timeout)
Concurrent requests: 6668 × 5 = 33,340!
```

**With 20 API Gateway instances:**
- Each instance has ~1,667 concurrent requests to Service A
- Connection pool (say 100 per instance) exhausted
- Requests queue up
- Memory exhausted
- Gateway OOM killed

**Retries during an outage = death spiral.**

---

## The Insight

**Retries are good when:** Failure is transient (network blip, temporary timeout)

**Retries are bad when:** System is genuinely overloaded (adds load to already-overloaded system)

**The question:** How do you know the difference?

---

## Retry Strategy in Go

```go
package retry

import (
    "context"
    "fmt"
    "math"
    "math/rand"
    "net/http"
    "time"
)

type RetryConfig struct {
    MaxRetries    int
    BaseDelay     time.Duration
    MaxDelay      time.Duration
    JitterEnabled bool
}

type RetryableError struct {
    Err       error
    Retryable bool
}

func (e *RetryableError) Error() string {
    return e.Err.Error()
}

func (e *RetryableError) Unwrap() error {
    return e.Err
}

// IsRetryable returns true if error is worth retrying
func IsRetryable(err error) bool {
    if err == nil {
        return false
    }

    // Network errors: retry
    if netErr, ok := err.(interface{ Timeout() bool }); ok && netErr.Timeout() {
        return true
    }

    // HTTP errors: only retry on specific codes
    if httpErr, ok := err.(*HTTPError); ok {
        // Retry on: 408 (timeout), 429 (rate limit), 500+, 503, 504
        // Don't retry on: 400 (bad request), 401/403 (auth), 404 (not found), 5xx (server overloaded)
        switch httpErr.StatusCode {
        case 408, 429:
            return true
        case 500, 502, 503, 504:
            // Only retry on server errors if not due to overload
            // In real systems: check error body or response headers
            return false // Fail fast on 5xx
        }
    }

    return false
}

type HTTPError struct {
    StatusCode int
    Err        error
}

func (e *HTTPError) Error() string {
    return fmt.Sprintf("HTTP %d: %v", e.StatusCode, e.Err)
}

// CalculateDelay with exponential backoff and jitter
func CalculateDelay(attempt int, config RetryConfig) time.Duration {
    // Exponential backoff: base * 2^attempt
    exponentialDelay := float64(config.BaseDelay) * math.Pow(2, float64(attempt))

    // Cap at max delay
    if exponentialDelay > float64(config.MaxDelay) {
        exponentialDelay = float64(config.MaxDelay)
    }

    delay := time.Duration(exponentialDelay)

    if config.JitterEnabled {
        // Add jitter: ±25% of delay
        jitter := time.Duration(float64(delay) * 0.25 * (2*rand.Float64() - 1))
        delay += jitter
    }

    return delay
}

// DoWithRetry executes fn with retry logic
func DoWithRetry(ctx context.Context, config RetryConfig, fn func() error) error {
    var lastErr error

    for attempt := 0; attempt <= config.MaxRetries; attempt++ {
        if attempt > 0 {
            delay := CalculateDelay(attempt-1, config)
            select {
            case <-time.After(delay):
            case <-ctx.Done():
                return ctx.Err()
            }
        }

        err := fn()
        if err == nil {
            return nil
        }

        lastErr = err

        // Check if error is retryable
        if !IsRetryable(err) {
            return err // Don't retry non-retryable errors
        }

        // Log retry attempt
        fmt.Printf("Attempt %d failed: %v, retrying after %v\n", attempt, err, CalculateDelay(attempt, config))
    }

    return fmt.Errorf("max retries exceeded: %w", lastErr)
}

// Example usage for HTTP client
type HTTPClient struct {
    client      *http.Client
    retryConfig RetryConfig
}

func NewHTTPClient(retryConfig RetryConfig) *HTTPClient {
    return &HTTPClient{
        client:      &http.Client{Timeout: 5 * time.Second},
        retryConfig: retryConfig,
    }
}

func (c *HTTPClient) Do(req *http.Request) (*http.Response, error) {
    var resp *http.Response

    err := DoWithRetry(req.Context(), c.retryConfig, func() error {
        var err error
        resp, err = c.client.Do(req)
        if err != nil {
            return err // Network error - might be retryable
        }

        // Check status code
        if resp.StatusCode >= 400 {
            resp.Body.Close()
            return &HTTPError{StatusCode: resp.StatusCode, Err: fmt.Errorf("HTTP %d", resp.StatusCode)}
        }

        return nil
    })

    return resp, err
}
```

---

## Better Retry Configuration

```go
// Conservative retry config for production
var ProductionRetryConfig = RetryConfig{
    MaxRetries:    2,                   // Only retry twice
    BaseDelay:     100 * time.Millisecond,
    MaxDelay:      1 * time.Second,
    JitterEnabled: true,                // Prevent thundering herd
}

// Aggressive retry config for internal services
var InternalRetryConfig = RetryConfig{
    MaxRetries:    5,
    BaseDelay:     50 * time.Millisecond,
    MaxDelay:      2 * time.Second,
    JitterEnabled: true,
}

// No retries for critical writes (fail fast)
var NoRetryConfig = RetryConfig{
    MaxRetries:    0,
    BaseDelay:     0,
    MaxDelay:      0,
    JitterEnabled: false,
}
```

**Key insight:** Different operations need different retry strategies.

---

## Quick Check

Before moving on, make sure you understand:

1. What happens when retries occur during an outage? (Adds load to overloaded system)
2. Why is retry on 5xx dangerous? (Server is already overloaded, retries make it worse)
3. What errors should be retried? (Network blips, timeouts, rate limits)
4. What errors should NOT be retried? (5xx server errors, 4xx client errors)
5. What's exponential backoff with jitter? (Increasing delay with randomness to prevent synchronized retries)

---

**Continue to `step-02.md`**
