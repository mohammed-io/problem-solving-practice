# Solution: Metrics Cardinality Management

---

## Root Cause Analysis

**The mistake:** Adding high-cardinality labels (`user_id`, `request_id`) to metrics caused time series explosion.

```
Before: 4,000 time series (manageable)
After: 4,000,000,000 time series (impossible)
```

**Why Prometheus struggled:**
- Each time series stored separately in memory
- Metadata per series: ~100 bytes
- Queries must scan all matching series
- Compaction became too slow

---

## Complete Solution

### 1. Metrics Design Framework

**USE + RED method:**

```go
package metrics

import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promauto"
)

var (
    // RED Method (Request, Error, Duration)
    httpRequestsTotal = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "http_requests_total",
            Help: "Total number of HTTP requests",
        },
        []string{"method", "endpoint", "status"},  // Low cardinality only
    )

    httpRequestDuration = promauto.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "http_request_duration_seconds",
            Help:    "HTTP request latency",
            Buckets: prometheus.DefBuckets,
        },
        []string{"method", "endpoint"},
    )

    // USE Method (Utilization, Saturation, Errors)
    cpuUsageSeconds = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "node_cpu_seconds_total",
            Help: "Total CPU time spent",
        },
        []string{"mode", "cpu"},  // mode=user/system/idle, cpu=0-63
    )

    memoryAvailable = promauto.NewGaugeVec(
        prometheus.GaugeOpts{
            Name: "node_memory_available_bytes",
            Help: "Available memory",
        },
        []string{},  // No labels needed
    )
)
```

### 2. High-Cardinality Alternatives

**Pattern decision tree:**

```
                    ┌─────────────────────┐
                    │   What do you       │
                    │   need to track?    │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
         Aggregates         Per-Request      Per-User
         (sum, count)       (details)        (who did it)
              │                │                │
              ▼                ▼                ▼
         Metrics           Traces           Logs
         (Prometheus)      (Tempo/Jaeger)  (Loki/ES)
```

**Implementation:**

```go
package telemetry

import (
    "context"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/trace"
    "github.com/prometheus/client_golang/prometheus"
)

// 1. Metrics for aggregates (low cardinality)
var httpRequestsTotal = prometheus.NewCounterVec(
    prometheus.CounterOpts{Name: "http_requests_total"},
    []string{"method", "endpoint", "status"},
)

// 2. Traces for per-request details (high cardinality)
var tracer = otel.Tracer("http")

func HandleRequest(w http.ResponseWriter, r *http.Request) {
    ctx, span := tracer.Start(r.Context(), "HandleRequest")
    defer span.End()

    // Add high-cardinality attributes to span
    span.SetAttributes(
        attribute.String("user_id", getUserID(r)),
        attribute.String("request_id", getReqID(r)),
        attribute.String("user_agent", r.UserAgent()),
    )

    // 3. Logs for detailed records
    log.Info("request",
        "user_id", getUserID(r),
        "request_id", getReqID(r),
        "method", r.Method,
        "endpoint", r.URL.Path,
    )

    // 4. Metrics for aggregates
    httpRequestsTotal.WithLabelValues(
        r.Method,
        r.URL.Path,
        "200",
    ).Inc()
}
```

### 3. Cardinality Monitoring

**Real-time cardinality tracking:**

```go
package metrics

import (
    "sync"
    "time"
)

type CardinalityMonitor struct {
    mu       sync.RWMutex
    metrics  map[string]*MetricInfo
    maxSeries int
}

type MetricInfo struct {
    labels    map[string]map[string]bool  // label → values
    seriesSet map[string]struct{}         // unique series
}

func NewCardinalityMonitor(maxSeries int) *CardinalityMonitor {
    return &CardinalityMonitor{
        metrics:   make(map[string]*MetricInfo),
        maxSeries: maxSeries,
    }
}

func (m *CardinalityMonitor) Record(metricName string, labels prometheus.Labels) error {
    m.mu.Lock()
    defer m.mu.Unlock()

    info, exists := m.metrics[metricName]
    if !exists {
        info = &MetricInfo{
            labels:    make(map[string]map[string]bool),
            seriesSet: make(map[string]struct{}),
        }
        m.metrics[metricName] = info
    }

    // Track unique label values
    for k, v := range labels {
        if info.labels[k] == nil {
            info.labels[k] = make(map[string]bool)
        }
        info.labels[k][v] = true
    }

    // Create series key
    seriesKey := seriesKey(labels)
    info.seriesSet[seriesKey] = struct{}{}

    // Check cardinality
    if len(info.seriesSet) > m.maxSeries {
        return fmt.Errorf("metric %s exceeds max series: %d",
            metricName, len(info.seriesSet))
    }

    return nil
}

func (m *CardinalityMonitor) GetCardinality(metricName string) int {
    m.mu.RLock()
    defer m.mu.RUnlock()

    if info, exists := m.metrics[metricName]; exists {
        return len(info.seriesSet)
    }
    return 0
}

func (m *CardinalityMonitor) GetLabelCardinality(metricName, labelName string) int {
    m.mu.RLock()
    defer m.mu.RUnlock()

    if info, exists := m.metrics[metricName]; exists {
        if values, exists := info.labels[labelName]; exists {
            return len(values)
        }
    }
    return 0
}

func seriesKey(labels prometheus.Labels) string {
    parts := make([]string, 0, len(labels))
    for k, v := range labels {
        parts = append(parts, fmt.Sprintf("%s=%s", k, v))
    }
    sort.Strings(parts)
    return strings.Join(parts, ",")
}

// Use in your metrics
var monitor = NewCardinalityMonitor(10000)

func RecordRequest(method, endpoint, status string) {
    labels := prometheus.Labels{
        "method":   method,
        "endpoint": endpoint,
        "status":   status,
    }

    if err := monitor.Record("http_requests_total", labels); err != nil {
        log.Error("cardinality limit exceeded", "error", err)
        return
    }

    httpRequestsTotal.With(labels).Inc()
}
```

**Prometheus recording rule for tracking:**

```yaml
# record_cardinality.yml
groups:
  - name: cardinality_tracking
    interval: 1m
    rules:
      # Track cardinality of each metric
      - record: metric_cardinality
        expr: |
          count by (__name__) ({__name__=~".+"})

      # Track total series
      - record: total_series_count
        expr: |
          count({__name__=~".+"})

      # Find top cardinality metrics
      - record: top_cardinality_metrics
        expr: |
          topk(20, metric_cardinality)
```

### 4. Safe Metric Collection

**Wrapper that enforces limits:**

```go
package promutil

import (
    "github.com/prometheus/client_golang/prometheus"
)

type SafeCounterVec struct {
    inner       *prometheus.CounterVec
    maxSeries   int
    seriesCount map[string]int
    mu          sync.RWMutex
    disabled    bool
}

func NewSafeCounterVec(opts prometheus.CounterOpts, labelNames []string, maxSeries int) *SafeCounterVec {
    return &SafeCounterVec{
        inner:       prometheus.NewCounterVec(opts, labelNames),
        maxSeries:   maxSeries,
        seriesCount: make(map[string]int),
    }
}

func (s *SafeCounterVec) With(labels prometheus.Labels) prometheus.Counter {
    if s.disabled {
        // Return no-op counter
        return prometheus.NewCounter(prometheus.CounterOpts{})
    }

    key := seriesKey(labels)

    s.mu.Lock()
    count := s.seriesCount[key]
    if count == 0 {
        if len(s.seriesCount) >= s.maxSeries {
            s.mu.Unlock()
            log.Warn("max series exceeded, metric disabled",
                "max", s.maxSeries)
            s.disabled = true
            return prometheus.NewCounter(prometheus.CounterOpts{})
        }
    }
    s.seriesCount[key]++
    s.mu.Unlock()

    return s.inner.With(labels)
}

func (s *SafeCounterVec) Describe(ch chan<- *prometheus.Desc) {
    s.inner.Describe(ch)
}

func (s *SafeCounterVec) Collect(ch chan<- prometheus.Metric) {
    if !s.disabled {
        s.inner.Collect(ch)
    }
}

// Usage
var httpRequestsTotal = NewSafeCounterVec(
    prometheus.CounterOpts{
        Name: "http_requests_total",
        Help: "Total HTTP requests",
    },
    []string{"method", "endpoint", "status"},
    10000,  // Max 10,000 series
)
```

---

## Trade-offs

| Approach | Pros | Cons | Use Case |
|----------|------|------|----------|
| **All metrics** | Complete visibility | Can't scale | Small systems |
| **Label limits** | Controlled growth | Drop data when limit hit | Medium systems |
| **Logs + Metrics** | Full detail, scalable | Multiple systems | Large systems |
| **Sampling** | Reduces cardinality | Lose some data | Very high scale |

**Recommendation:** Metrics for aggregates (RED/USE), logs/traces for high-cardinality data.

---

## Quick Checklist

**Before adding a metric:**
- [ ] Calculated cardinality (product of label values)
- [ ] Total series < 10,000 per metric
- [ ] Labels have < 100 unique values each
- [ ] Considered histogram for numeric ranges
- [ ] Documented what the metric measures
- [ ] Set up alert for cardinality growth

**For high-cardinality data:**
- [ ] Use logs (Loki/Elasticsearch)
- [ ] Use traces (Tempo/Jaeger)
- [ ] Pre-aggregate before metric recording
- [ ] Use sampling for very high scale

---

**Next Problem:** `observability/obs-102-tracing-gaps/`
