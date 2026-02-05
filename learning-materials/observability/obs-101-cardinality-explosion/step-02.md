# Step 2: Prevention and Alternatives

---

## Metrics Design Principles

**The RED method:**

```
R - Rate: Requests per second
E - Errors: Error rate
D - Duration: Latency

For each endpoint, track:
  - request_rate{method, endpoint, status}
  - error_rate{method, endpoint}
  - latency{method, endpoint} (histogram)
```

**The USE method:**

```
U - Utilization: Percentage of resource used
S - Saturation: How loaded is the resource
E - Errors: Error count

For each resource (CPU, memory, disk, network):
  - cpu_utilization{instance, mode}
  - memory_utilization{instance}
  - disk_saturation{instance, device}
```

---

## Safe Metrics Patterns

**Pattern 1: Use enums, not IDs**

```go
// BAD: user_id as label
var requestsByUser = prometheus.NewCounterVec(
    prometheus.CounterOpts{Name: "requests_total"},
    []string{"user_id"},  // 1M+ unique values
)

// GOOD: Use tier or segment
var requestsByTier = prometheus.NewCounterVec(
    prometheus.CounterOpts{Name: "requests_total"},
    []string{"user_tier"},  // free, pro, enterprise (3 values)
)
```

**Pattern 2: Use bucketed values**

```go
// BAD: Exact age as label
var usersByAge = prometheus.NewGaugeVec(
    prometheus.GaugeOpts{Name: "users_total"},
    []string{"age"},  // 0-100+ = 100+ labels
)

// GOOD: Age ranges
var usersByAgeRange = prometheus.NewGaugeVec(
    prometheus.GaugeOpts{Name: "users_total"},
    []string{"age_range"},  // 18-24, 25-34, 35-44, 45-54, 55+
)
```

**Pattern 3: Use quantiles via histogram**

```go
// BAD: Track every percentile as label
var latencyByPercentile = prometheus.NewGaugeVec(
    prometheus.GaugeOpts{Name: "latency_seconds"},
    []string{"percentile"},  // p50, p90, p95, p99 = 4 labels (OK)
)

// BETTER: Use histogram (native quantiles)
var latency = prometheus.NewHistogram(
    prometheus.HistogramOpts{
        Name:    "latency_seconds",
        Buckets: prometheus.ExponentialBuckets(0.001, 2, 10),
    },
)

// Query quantiles
histogram_quantile(0.95, rate(latency_seconds_bucket[5m]))
```

---

## Pre-commit Cardinality Check

**Git hook to prevent high cardinality:**

```bash
#!/bin/bash
# pre-commit: Check for high-cardinality labels

echo "Checking metrics cardinality..."

# Find all Prometheus metric definitions
grep -r "prometheus\.(NewCounterVec\|NewGaugeVec\|NewHistogramVec\|NewSummaryVec)" \
    --include="*.go" . | \
while read -r line; do
    # Extract label names from []string
    if echo "$line" | grep -q 'user_id\|request_id\|session_id\|trace_id'; then
        echo "✗ HIGH CARDINALITY LABEL FOUND:"
        echo "  $line"
        echo ""
        echo "These labels have very high cardinality."
        echo "Please remove them or use an alternative approach."
        exit 1
    fi
done

echo "✓ No high-cardinality labels found"
exit 0
```

**Go version:**

```go
// +build ignore

package main

import (
    "fmt"
    "go/ast"
    "go/parser"
    "go/token"
    "os"
    "strings"
)

var highCardinalityLabels = map[string]bool{
    "user_id":     true,
    "request_id":  true,
    "session_id":  true,
    "trace_id":    true,
    "span_id":     true,
    "ip":          true,
    "email":       true,
}

func checkMetrics(filePath string) error {
    fset := token.NewFileSet()
    node, err := parser.ParseFile(fset, filePath, nil, parser.ParseComments)
    if err != nil {
        return err
    }

    foundIssues := false

    ast.Inspect(node, func(n ast.Node) bool {
        call, ok := n.(*ast.CallExpr)
        if !ok {
            return true
        }

        // Check for prometheus metric constructors
        if fun, ok := call.Fun.(*ast.SelectorExpr); ok {
            if pkg, ok := fun.X.(*ast.Ident); ok && pkg.Name == "prometheus" {
                switch fun.Sel.Name {
                case "NewCounterVec", "NewGaugeVec", "NewHistogramVec", "NewSummaryVec":
                    // Check the labels argument
                    if len(call.Args) >= 2 {
                        if labels, ok := call.Args[1].(*ast.CompositeLit); ok {
                            for _, elt := range labels.Elts {
                                if basic, ok := elt.(*ast.BasicLit); ok {
                                    label := strings.Trim(basic.Value, `"`)
                                    if highCardinalityLabels[label] {
                                        fmt.Printf("%s: high cardinality label '%s'\n",
                                            filePath, label)
                                        foundIssues = true
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        return true
    })

    if foundIssues {
        return fmt.Errorf("high cardinality labels found")
    }
    return nil
}

func main() {
    if len(os.Args) < 2 {
        fmt.Println("Usage: check-metrics <file.go>")
        os.Exit(1)
    }

    if err := checkMetrics(os.Args[1]); err != nil {
        fmt.Println("Error:", err)
        os.Exit(1)
    }
}
```

---

## Real-time Cardinality Monitoring

**Alert on high cardinality:**

```yaml
# prometheus_rules.yml
groups:
  - name: cardinality
    rules:
      # Alert when metric exceeds 100k series
      - alert: HighCardinalityMetric
        expr: |
          topk(100,
            count by (__name__) ({__name__=~".+"})
          ) > 100000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High cardinality metric detected"
          description: "Metric {{ $labels.__name__ }} has {{ $value }} series"

      # Alert when total series exceeds threshold
      - alert: PrometheusHighCardinality
        expr: |
          prometheus_tsdb_series_count_total > 1000000
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Prometheus high total series count"
          description: "Prometheus has {{ $value }} total series"
```

---

## When High Cardinality is OK

**Limited use cases:**

```go
// Scenario 1: Very small scale
// If you have <100 users, user_id is fine!

// Scenario 2: Short retention
// If you only keep 1 hour of data, cardinality matters less

// Scenario 3: Aggregation before recording
// Pre-aggregate in application, record only aggregates
type UserMetrics struct {
    requestCount  map[string]int64
    totalDuration map[string]time.Duration
    mu            sync.Mutex
}

func (m *UserMetrics) Record(userID string, duration time.Duration) {
    m.mu.Lock()
    defer m.mu.Unlock()

    m.requestCount[userID]++
    m.totalDuration[userID] += duration

    // Flush aggregated metrics every minute
    if len(m.requestCount) > 1000 {
        m.flush()
    }
}

func (m *UserMetrics) flush() {
    // Record top users only
    for userID, count := range m.topUsers(10) {
        requests.WithLabelValues(userID).Add(float64(count))
    }
    // Reset
    m.requestCount = make(map[string]int64)
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's the RED method? (Rate, Errors, Duration - for monitoring endpoints)
2. What's the USE method? (Utilization, Saturation, Errors - for monitoring resources)
3. What's a safe pattern instead of user_id labels? (Use user_tier or other low-cardinality attributes)
4. What's histogram_quantile? (PromQL function to calculate percentiles from histogram buckets)
5. What's a pre-commit hook for cardinality? (Git hook that checks for high-cardinality labels before commit)

---

**Continue to `solution.md`**
