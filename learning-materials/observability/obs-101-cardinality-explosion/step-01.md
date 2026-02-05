# Step 1: Understanding Cardinality

---

## Calculating Cardinality

**The formula:**

```
Total time series = (cardinality of label 1)
                  × (cardinality of label 2)
                  × (cardinality of label 3)
                  × ...
```

**Example calculation:**

```python
from dataclasses import dataclass
from typing import Dict

@dataclass
class LabelConfig:
    name: str
    cardinality: int

def calculate_cardinality(labels: list[LabelConfig]) -> int:
    """Calculate total time series for a metric."""
    total = 1
    for label in labels:
        total *= label.cardinality
    return total

# Original metric (low cardinality)
original = [
    LabelConfig("method", 4),      # GET, POST, PUT, DELETE
    LabelConfig("endpoint", 50),   # API endpoints
    LabelConfig("status", 20),     # HTTP status codes
]
print(f"Original cardinality: {calculate_cardinality(original):,}")
# Output: 4,000

# After adding user_id
with_user_id = [
    LabelConfig("method", 4),
    LabelConfig("endpoint", 50),
    LabelConfig("status", 20),
    LabelConfig("user_id", 1_000_000),  # 1M users!
]
print(f"With user_id: {calculate_cardinality(with_user_id):,}")
# Output: 4,000,000,000

# After adding request_id (infinite)
print("With request_id: INFINITE (every request adds new series)")
```

---

## Cardinality Guidelines

**Safe cardinality per label:**

| Cardinality Range | Example Label | Safe? |
|-------------------|---------------|-------|
| < 10 | method, status | ✓ Safe |
| 10 - 100 | endpoint, region | ✓ Generally safe |
| 100 - 1,000 | customer_tier, datacenter | ⚠️ Use caution |
| 1,000 - 10,000 | user_group | ⚠️ Consider alternatives |
| > 10,000 | user_id, request_id | ✗ NEVER use as label |

**Total metric cardinality:**

| Total Series | Memory Usage | Query Performance |
|--------------|--------------|-------------------|
| < 10,000 | Minimal | Excellent |
| 10,000 - 100,000 | < 1 GB | Good |
| 100,000 - 1,000,000 | 1-10 GB | Degrading |
| > 1,000,000 | > 10 GB | Poor |
| > 10,000,000 | > 100 GB | Unusable |

---

## Detecting High Cardinality

**Query to find high-cardinality metrics:**

```promql
# Find metrics with most series
topk(10, count by (__name__) ({__name__=~".+"}))

# Check specific metric cardinality
count(http_requests_total)
```

**Python tool to scan metrics:**

```python
import re
import requests
from collections import defaultdict

def scan_cardinality(prometheus_url: str) -> dict:
    """Scan all metrics and report cardinality."""
    # Get all metric names
    response = requests.get(f"{prometheus_url}/api/v1/label/__name__/values")
    metric_names = response.json()['data']

    results = {}

    for metric in metric_names:
        # Query count of series for this metric
        query = f'count({metric})'
        response = requests.get(f"{prometheus_url}/api/v1/query", params={'query': query})
        result = response.json()['data']['result']

        if result:
            count = int(result[0]['value'][1])
            results[metric] = count

    # Sort by cardinality
    return dict(sorted(results.items(), key=lambda x: x[1], reverse=True))

# Usage
cardinality = scan_cardinality("http://prometheus:9090")
for metric, count in list(cardinality.items())[:10]:
    status = "✗ HIGH" if count > 100000 else "✓ OK"
    print(f"{metric}: {count:,} series {status}")
```

---

## Alternative: Use Histograms

**For high-cardinality numeric values:**

```go
// BAD: Each latency value creates new time series
var httpRequestDuration = prometheus.NewGaugeVec(
    prometheus.GaugeOpts{
        Name: "http_request_duration_ms",
        Help: "HTTP request duration",
    },
    []string{"user_id", "duration"},  // duration as label = BAD!
)

// GOOD: Use histogram with predefined buckets
var httpRequestDuration = prometheus.NewHistogramVec(
    prometheus.HistogramOpts{
        Name:    "http_request_duration_seconds",
        Help:    "HTTP request duration",
        Buckets: []float64{.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10},
    },
    []string{"endpoint"},  // Only low-cardinality labels
)

// Usage
httpRequestDuration.WithLabelValues("/api/users").Observe(duration.Seconds())
```

**Histogram adds fixed number of series:**

```
Histogram series = (number of buckets + sum + count + created) × label combinations

For our example:
  - Buckets: 11
  - + sum series: 1
  - + count series: 1
  - + created series: 1
  - Total per label combination: 14 series

For 50 endpoints:
  - Total series = 14 × 50 = 700 series ✓

Versus tracking per-user:
  - 1M users × 11 buckets = 11M series ✗
```

---

## Alternative: Use Logs for High Cardinality

**Logs are better for per-request data:**

```go
// Structured logging with high-cardinality fields
log.Info("HTTP request",
    "method", r.Method,
    "endpoint", r.URL.Path,
    "status", statusCode,
    "user_id", userID,      // OK for logs!
    "request_id", reqID,    // OK for logs!
    "duration_ms", duration.Milliseconds(),
)

// Logs don't have the same cardinality constraints
// Use Loki/Elasticsearch/Splunk to query logs
// Use metrics for aggregates, logs for details
```

**Metrics vs Logs vs Traces:**

```
┌────────────────────────────────────────────────────────────────────┐
│  Metrics                                                           │
│  - Aggregates (count, sum, avg)                                    │
│  - Low cardinality (method, status, endpoint)                      │
│  - Fast queries on large time ranges                               │
│  - Storage: Time-series database (Prometheus, Mimir)              │
├────────────────────────────────────────────────────────────────────┤
│  Logs                                                              │
│  - Detailed events (who did what)                                  │
│  - High cardinality (user_id, request_id)                          │
│  - Text search, filtering                                          │
│  - Storage: Log aggregation (Loki, Elasticsearch)                  │
├────────────────────────────────────────────────────────────────────┤
│  Traces                                                            │
│  - Request flow across services                                    │
│  - High cardinality (trace_id, span_id)                            │
│  - Duration, parent-child relationships                           │
│  - Storage: Trace backend (Tempo, Jaeger)                          │
└────────────────────────────────────────────────────────────────────┘
```

---

## Quick Check

Before moving on, make sure you understand:

1. How do you calculate total metric cardinality? (Multiply cardinality of all labels: label1 × label2 × label3...)
2. What's the safe cardinality range per label? (<10 safe, <100 generally safe, >10K never use)
3. Why is user_id a bad label? (Can have millions of unique values, explodes cardinality)
4. Why are histograms better for high-cardinality values? (Fixed number of buckets, predefined series)
5. What's the difference between metrics and logs? (Metrics = aggregates/low cardinality, Logs = detailed events/high cardinality)

---

**Continue to `step-02.md`**
