# Step 02: The Metrics Explosion Problem

---

## The Problem

The team is exporting **500+ metrics per service**:

```
Service A exports:
- http_requests_total{method="GET", path="/api/orders"}       ✓
- http_requests_total{method="GET", path="/api/items"}        ✓
- http_requests_total{method="POST", path="/api/orders"}      ✓
... (and 497 more)

❌ 50 services × 500 metrics = 25,000 time series
❌ Prometheus can't scrape fast enough
❌ Queries are slow
❌ Storage is expensive
```

---

## Question: What Causes Metric Explosion?

**Hint:** It's not the number of metrics. It's the **labels**.

```
GOOD (low cardinality):
http_requests_total{service="order-api", method="GET", status="200"}
→ 3 services × 4 methods × 5 status codes = 60 time series ✓

BAD (high cardinality):
http_requests_total{service="order-api", user_id="12345"}
→ 3 services × 1,000,000 users = 3,000,000 time series ✗
```

**Cardinality** = number of unique label combinations.

---

## The RED Method

Instead of measuring everything, measure what matters. Use the **RED method** for services:

| Letter | Stands For | What to Measure |
|--------|------------|-----------------|
| **R** | Rate | Requests per second |
| **E** | Errors | Error rate (5xx / total) |
| **D** | Duration | Request latency (p50, p95, p99) |

**That's it.** Just 3 metrics per service (or 4 with a histogram for duration).

---

## Code Example: The Right Way

```go
// BAD: 500+ metrics
func BadMetrics() {
    metrics.Counter("order_create_total")
    metrics.Counter("order_update_total")
    metrics.Counter("order_delete_total")
    metrics.Counter("order_get_total")
    metrics.Counter("order_list_total")
    metrics.Counter("order_item_add_total")
    // ... 494 more
}

// GOOD: 3-4 metrics using RED method
type ServiceMetrics struct {
    // R - Rate: Request counter
    Requests *prometheus.CounterVec

    // E - Errors: Error counter (derived from Requests with status label)
    // D - Duration: Latency histogram
    Duration *prometheus.HistogramVec
}

func NewServiceMetrics(serviceName string) *ServiceMetrics {
    return &ServiceMetrics{
        Requests: promauto.NewCounterVec(
            prometheus.CounterOpts{
                Name: "http_requests_total",
            },
            // Low cardinality labels only
            []string{"service", "method", "status"},
        ),

        Duration: promauto.NewHistogramVec(
            prometheus.HistogramOpts{
                Name:    "http_duration_seconds",
                Buckets: []float64{.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10},
            },
            []string{"service", "endpoint"},
        ),
    }
}

// Usage: ONE metric call per request
func (m *ServiceMetrics) RecordRequest(service, method, endpoint string, status int, duration time.Duration) {
    m.Requests.WithLabelValues(service, method, http.StatusText(status)).Inc()
    m.Duration.WithLabelValues(service, endpoint).Observe(duration.Seconds())
}

// Result: 3 services × 4 methods × 5 statuses × 10 endpoints = ~600 time series ✓
```

---

## What About Resource Metrics?

For resources (CPU, memory, disk), use the **USE method**:

| Letter | Stands For | What to Measure |
|--------|------------|-----------------|
| **U** | Utilization | % of resource being used |
| **S** | Saturation | How "full" is the resource |
| **E** | Errors | Error count |

```go
// USE method for resources
metrics.Gauge("cpu_usage_percent")
metrics.Gauge("memory_available_bytes")
metrics.Counter("disk_errors_total")
```

---

## Labels to Avoid

```
❌ NEVER use these as labels:
   - user_id, customer_id, account_id (unbounded)
   - request_id, trace_id, session_id (unique per request)
   - ip_address, email_address (PII + high cardinality)
   - timestamp (infinite values)

✅ USE these labels:
   - service (5-50 values)
   - method (5-10 values: GET, POST, etc.)
   - status (10-20 values: 200, 404, 500, etc.)
   - endpoint (50-200 values)
   - region (2-10 values)
```

---

## Quick Check

Before moving on, make sure you understand:

1. What causes metric explosion? (Labels, not metrics)
2. What is the RED method? (Rate, Errors, Duration)
3. What is the USE method? (Utilization, Saturation, Errors)
4. Which labels should you avoid? (High cardinality)

---

**Ready to tackle alerting? Read `step-03.md`**
