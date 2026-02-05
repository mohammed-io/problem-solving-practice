# Solution: Cascade Failure - Resilience Patterns

---

## Root Cause

**Four compounding failures:**

1. **No backpressure:** Gateway didn't slow down when services were slow
2. **Aggressive retries:** 3 retries × 5s timeout = 15s per failed request
3. **No circuit breaker:** Failing service stayed in rotation
4. **No bulkheads:** One service's failure affected all services

---

## Complete Solution

### 1. Retry with Exponential Backoff

```javascript
const retryConfig = {
    retries: 2,           // Max 2 retries (was 3)
    minTimeout: 50,       // Start at 50ms
    maxTimeout: 500,      // Cap at 500ms (was 5000ms!)
    factor: 2,            // Exponential: 50, 100, 200, 500
    randomize: true,      // Add jitter
    retryable: (error) => {
        // Only retry network errors, not 5xx
        return !error.response || error.response.status < 500;
    }
};
```

### 2. Circuit Breaker

```javascript
class CircuitBreaker {
    constructor(options = {}) {
        this.threshold = options.threshold || 0.5;  // 50% failure rate
        this.timeout = options.timeout || 30000;    // 30s open state
        this.halfOpenAttempts = options.halfOpenAttempts || 1;
        this.window = options.window || 10000;     // 10s sliding window

        this.state = 'closed';
        this.stats = {
            attempts: 0,
            successes: 0,
            failures: 0,
            lastFailureTime: 0
        };
        this.nextAttempt = 0;
    }

    async execute(fn) {
        if (this.state === 'open') {
            if (Date.now() >= this.nextAttempt) {
                this.state = 'half-open';
                this.stats.attempts = 0;
            } else {
                throw new CircuitBreakerOpenError('Circuit breaker open');
            }
        }

        this.stats.attempts++;

        try {
            const result = await fn();
            this.onSuccess();
            return result;
        } catch (error) {
            this.onFailure();
            throw error;
        }
    }

    onSuccess() {
        this.stats.successes++;

        if (this.state === 'half-open' && this.stats.successes >= this.halfOpenAttempts) {
            this.state = 'closed';
            this.resetStats();
        }
    }

    onFailure() {
        this.stats.failures++;
        this.stats.lastFailureTime = Date.now();

        const failureRate = this.stats.failures / this.stats.attempts;
        if (failureRate >= this.threshold) {
            this.state = 'open';
            this.nextAttempt = Date.now() + this.timeout;
        }
    }

    resetStats() {
        this.stats = {
            attempts: 0,
            successes: 0,
            failures: 0,
            lastFailureTime: 0
        };
    }

    getState() {
        return {
            state: this.state,
            attempts: this.stats.attempts,
            failures: this.stats.failures,
            failureRate: this.stats.attempts > 0
                ? this.stats.failures / this.stats.attempts
                : 0
        };
    }
}
```

### 3. Bulkheads (Connection Pools)

```javascript
const { Pool } = require('pg');

// Separate pools per service
const pools = {
    serviceA: new Pool({
        max: 50,              // Max 50 connections
        idleTimeoutMillis: 30000,
        connectionTimeoutMillis: 2000
    }),
    serviceB: new Pool({
        max: 50,
        idleTimeoutMillis: 30000,
        connectionTimeoutMillis: 2000
    }),
    serviceC: new Pool({
        max: 50,
        idleTimeoutMillis: 30000,
        connectionTimeoutMillis: 2000
    })
};

// Service A pool exhausted doesn't affect B or C
```

### 4. Timeout Budget

```javascript
// Timeout at each tier: total timeout < client timeout
const timeouts = {
    client: 5000,         // Client timeout: 5s
    gateway: 4000,        // Gateway has 4s to respond
    service: 3000,        // Service has 3s
    database: 1000        // DB query has 1s
};

app.get('/api/orders', async (req, res) => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeouts.service);

    try {
        const result = await fetch('http://service-a/orders', {
            signal: controller.signal
        });
        return res.json(result);
    } catch (error) {
        if (error.name === 'AbortError') {
            return res.status(504).json({ error: 'Gateway timeout' });
        }
        throw error;
    } finally {
        clearTimeout(timeout);
    }
});
```

### 5. Graceful Degradation

```javascript
app.get('/api/dashboard', async (req, res) => {
    const data = {
        user: null,
        orders: null,
        recommendations: null
    };

    // Try each service, continue on failure
    try {
        data.user = await fetchWithCircuitBreaker('http://service-a/user');
    } catch (error) {
        console.error('User service unavailable');
    }

    try {
        data.orders = await fetchWithCircuitBreaker('http://service-b/orders');
    } catch (error) {
        console.error('Order service unavailable');
        data.orders = { fallback: 'Recent orders unavailable' };
    }

    try {
        data.recommendations = await fetchWithCircuitBreaker('http://service-c/recs');
    } catch (error) {
        console.error('Recommendations unavailable');
        // Silently skip - not critical
    }

    return res.json(data);
});
```

---

## Systemic Prevention

### 1. Load Shedding

```javascript
// Prioritize critical requests
const priority = (req) => {
    if (req.path.startsWith('/api/checkout')) return 'critical';
    if (req.path.startsWith('/api/search')) return 'normal';
    return 'low';
};

app.use((req, res, next) => {
    if (systemLoad > 0.8 && priority(req) === 'low') {
        return res.status(503).json({ error: 'System overloaded, try again later' });
    }
    next();
});
```

### 2. Rate Limiting

```javascript
// Per-service rate limits
const rateLimiter = new RateLimiter({
    tokensPerInterval: 100,
    interval: 'second',
    fireInterval: 250
});

app.use('/api/service-a', rateLimiter.middleware());
```

### 3. Health Checks

```javascript
app.get('/health', async (req, res) => {
    const health = {
        status: 'healthy',
        services: {}
    };

    for (const [name, url] of services) {
        try {
            const start = Date.now();
            await fetch(url + '/health', { timeout: 1000 });
            health.services[name] = {
                status: 'healthy',
                latency: Date.now() - start
            };
        } catch (error) {
            health.services[name] = { status: 'unhealthy' };
            health.status = 'degraded';
        }
    }

    const statusCode = health.status === 'healthy' ? 200 : 503;
    return res.status(statusCode).json(health);
});
```

### 4. Monitoring

```promql
# Circuit breaker open
- alert: CircuitBreakerOpen
  expr: |
    circuit_breaker_state{state="open"} == 1
  for: 1m
  labels:
    severity: critical

# High failure rate
- alert: HighFailureRate
  expr: |
    rate(requests_failed_total{service="service-a"}[5m])
    / rate(requests_total{service="service-a"}[5m]) > 0.3
  labels:
    severity: warning

# Connection pool exhausted
- alert: ConnectionPoolExhausted
  expr: |
    pool_active_connections / pool_max_connections > 0.9
  labels:
    severity: critical
```

---

## Trade-offs

| Pattern | Benefit | Cost |
|---------|---------|------|
| **Circuit breaker** | Prevents retry storms | Added latency, complexity |
| **Bulkheads** | Isolates failures | Resource overhead |
| **Graceful degradation** | Partial service during outage | Complex response handling |
| **Load shedding** | Protects system | Drops requests, bad UX |
| **Exponential backoff** | Reduces retry storm | Slower recovery |

---

## Real Incident Reference

**Netflix (2012):** Cascade failure in API gateway during AWS outage. Fixed by implementing Hystrix (circuit breakers, bulkheads, fallbacks). Led to Chaos Monkey testing.

**Amazon (2011):** Network partition caused cascading failures. Fixed by better timeouts, retries with backoff, and graceful degradation.

---

**Next Problem:** `advanced/incident-102-thundering-herd/`
