---
name: des-003-observability-design
description: Designing observability strategy for distributed systems - metrics, logs, traces, dashboards, and alerting
difficulty: Advanced
category: Design Review
level: Principal Engineer
---

# Solution: Observability Strategy

---

## Overview

A production-ready observability strategy requires:
1. **Three Pillars:** Metrics, Logs, Traces
2. **Metric Strategy:** RED + USE methods, control cardinality
3. **Alerting:** Symptom-based, SLO-driven
4. **SLOs:** Defined, tracked, with error budget

---

## 1. Three Pillars Implementation

### Distributed Tracing with OpenTelemetry

```go
package tracing

import (
    "context"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/exporters/jaeger"
    "go.opentelemetry.io/otel/sdk/resource"
    tracesdk "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/otel/semconv/v1.4.0"
    "go.opentelemetry.io/otel/trace"
)

type Tracer struct {
    tracer trace.Tracer
}

func NewTracer(serviceName string) (*Tracer, error) {
    // Create Jaeger exporter
    exp, err := jaeger.New(jaeger.WithCollectorEndpoint(
        jaeger.WithEndpoint("http://jaeger:14268/api/traces"),
    ))
    if err != nil {
        return nil, err
    }

    // Create tracer provider
    tp := tracesdk.NewTracerProvider(
        tracesdk.WithBatcher(exp),
        tracesdk.WithResource(resource.NewWithAttributes(
            semconv.SchemaURL,
            semconv.ServiceNameKey.String(serviceName),
        )),
    )

    otel.SetTracerProvider(tp)

    return &Tracer{
        tracer: otel.Tracer(serviceName),
    }, nil
}

func (t *Tracer) StartSpan(ctx context.Context, name string) (context.Context, trace.Span) {
    return t.tracer.Start(ctx, name)
}

// Usage in HTTP handler
func (h *OrderHandler) GetOrders(w http.ResponseWriter, r *http.Request) {
    ctx, span := h.tracer.StartSpan(r.Context(), "GetOrders")
    defer span.End()

    // Add attributes
    span.SetAttributes(
        attribute.String("user.id", getUserID(ctx)),
        attribute.String("order.id", getOrderId(r)),
    )

    // Business logic
    orders, err := h.service.GetOrders(ctx)
    if err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, "failed to get orders")
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }

    json.NewEncoder(w).Encode(orders)
    span.SetStatus(codes.Ok, "success")
}

// Propagate trace context across services
func (c *Client) CallOrderService(ctx context.Context, orderID string) error {
    ctx, span := c.tracer.StartSpan(ctx, "CallOrderService")
    defer span.End()

    // Headers will automatically include trace context
    req, _ := http.NewRequestWithContext(ctx, "GET",
        "http://order-service/orders/"+orderID, nil)

    resp, err := c.httpClient.Do(req)
    // Trace continues in OrderService
    return err
}
```

### Structured Logging

```go
package logging

import (
    "context"
    "go.opentelemetry.io/otel/trace"
    "go.uber.org/zap"
    "go.uber.org/zap/zapcore"
)

type Logger struct {
    zap *zap.Logger
}

func NewLogger(serviceName string) *Logger {
    config := zap.NewProductionConfig()
    config.EncoderConfig.TimeKey = "timestamp"
    config.EncoderConfig.EncodeTime = zapcore.ISO8601TimeEncoder

    logger, _ := config.Build()
    logger = logger.With(zap.String("service", serviceName))

    return &Logger{zap: logger}
}

func (l *Logger) WithRequest(ctx context.Context) *zap.Logger {
    spanContext := trace.SpanFromContext(ctx).SpanContext()

    fields := []zap.Field{}
    if spanContext.IsValid() {
        fields = append(fields,
            zap.String("trace_id", spanContext.TraceID().String()),
            zap.String("span_id", spanContext.SpanID().String()),
        )
    }

    return l.zap.With(fields...)
}

func (l *Logger) Error(ctx context.Context, msg string, fields ...zap.Field) {
    l.WithRequest(ctx).Error(msg, fields...)
}

func (l *Logger) Info(ctx context.Context, msg string, fields ...zap.Field) {
    l.WithRequest(ctx).Info(msg, fields...)
}

// Usage
func (h *OrderHandler) GetOrders(w http.ResponseWriter, r *http.Request) {
    logger.Info(r.Context(), "handling GetOrders request",
        zap.String("user_id", getUserID(r)),
        zap.String("order_id", getOrderId(r)),
    )

    orders, err := h.service.GetOrders(r.Context())
    if err != nil {
        logger.Error(r.Context(), "failed to get orders",
            zap.Error(err),
            zap.String("order_id", getOrderId(r)),
        )
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }

    logger.Info(r.Context(), "successfully retrieved orders",
        zap.Int("count", len(orders)),
    )
}
```

---

## 2. Metrics Implementation

### Prometheus Metrics with RED Method

```go
package metrics

import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promauto"
    "net/http"
    "time"
)

type Metrics struct {
    // RED Method: Rate, Errors, Duration
    RequestsTotal *prometheus.CounterVec
    ErrorsTotal   *prometheus.CounterVec
    Duration      *prometheus.HistogramVec

    // Resource metrics (USE method)
    CPUUsage    prometheus.Gauge
    MemoryUsage prometheus.Gauge
}

func NewMetrics(serviceName string) *Metrics {
    return &Metrics{
        RequestsTotal: promauto.NewCounterVec(
            prometheus.CounterOpts{
                Name: "http_requests_total",
                Help: "Total HTTP requests",
            },
            []string{"service", "method", "status", "endpoint"},
        ),

        ErrorsTotal: promauto.NewCounterVec(
            prometheus.CounterOpts{
                Name: "http_errors_total",
                Help: "Total HTTP errors (5xx)",
            },
            []string{"service", "error_type"},
        ),

        Duration: promauto.NewHistogramVec(
            prometheus.HistogramOpts{
                Name:    "http_duration_seconds",
                Help:    "HTTP request duration",
                Buckets: []float64{.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10},
            },
            []string{"service", "endpoint"},
        ),

        CPUUsage: promauto.NewGauge(prometheus.GaugeOpts{
            Name: "process_cpu_usage",
            Help: "CPU usage percentage",
        }),

        MemoryUsage: promauto.NewGauge(prometheus.GaugeOpts{
            Name: "process_memory_bytes",
            Help: "Memory usage in bytes",
        }),
    }
}

func (m *Metrics) RecordRequest(service, method, endpoint string, status int, duration time.Duration) {
    m.Requests.WithLabelValues(service, method, http.StatusText(status), endpoint).Inc()

    if status >= 500 {
        m.ErrorsTotal.WithLabelValues(service, "5xx").Inc()
    }

    m.Duration.WithLabelValues(service, endpoint).Observe(duration.Seconds())
}
```

### Metrics Middleware

```go
package middleware

import (
    "strconv"
    "time"
)

func MetricsMiddleware(metrics *metrics.Metrics) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            start := time.Now()

            // Wrap response writer to capture status
            ww := &responseWriter{ResponseWriter: w, status: 200}

            defer func() {
                duration := time.Since(start)
                metrics.RecordRequest(
                    "order-service",
                    r.Method,
                    r.URL.Path,
                    ww.status,
                    duration,
                )
            }()

            next.ServeHTTP(ww, r)
        })
    }
}

type responseWriter struct {
    http.ResponseWriter
    status int
}

func (w *responseWriter) WriteHeader(statusCode int) {
    w.status = statusCode
    w.ResponseWriter.WriteHeader(statusCode)
}

// For Chi router
func Middleware(serviceName string) func(http.Handler) http.Handler {
    m := metrics.NewMetrics(serviceName)
    return MetricsMiddleware(m)
}
```

---

## 3. SLO Implementation

### Error Budget Calculator

```go
package slo

import (
    "time"
)

type ErrorBudget struct {
    TargetPercent    float64       // 99.9
    Period           time.Duration // 30 days
    totalRequests    float64
    badRequests      float64
}

func NewErrorBudget(target float64, period time.Duration) *ErrorBudget {
    return &ErrorBudget{
        TargetPercent: target,
        Period:        period,
    }
}

func (eb *ErrorBudget) RecordRequest(success bool) {
    eb.totalRequests++
    if !success {
        eb.badRequests++
    }
}

func (eb *ErrorBudget) Availability() float64 {
    if eb.totalRequests == 0 {
        return 100
    }
    return 100 * (1 - eb.badRequests/eb.totalRequests)
}

func (eb *ErrorBudget) BudgetRemaining() float64 {
    allowedErrorRate := (100 - eb.TargetPercent) / 100
    actualErrorRate := eb.badRequests / eb.totalRequests

    if actualErrorRate == 0 {
        return 100
    }

    burnRate := actualErrorRate / allowedErrorRate
    return 100 - (burnRate * 100)
}

func (eb *ErrorBudget) BurnRate() float64 {
    allowedErrorRate := (100 - eb.TargetPercent) / 100
    actualErrorRate := eb.badRequests / eb.totalRequests
    return actualErrorRate / allowedErrorRate
}

func (eb *ErrorBudget) TimeToExhaust() time.Duration {
    burnRate := eb.BurnRate()
    if burnRate <= 1 {
        return time.Duration(1<<63 - 1) // Infinite
    }
    return time.Duration(float64(eb.Period) / burnRate)
}
```

### SLO Monitor

```go
package slo

import (
    "context"
    "fmt"
    "sync"
    "time"
)

type SLOConfig struct {
    Name              string
    TargetPercent     float64
    Period            time.Duration
    AlertThresholds   struct {
        WarningBurnRate  float64 // 2x
        CriticalBurnRate float64 // 10x
    }
}

type SLOMonitor struct {
    configs map[string]*SLOConfig
    budgets map[string]*ErrorBudget
    mu      sync.RWMutex
}

func NewSLOMonitor() *SLOMonitor {
    return &SLOMonitor{
        configs: make(map[string]*SLOConfig),
        budgets: make(map[string]*ErrorBudget),
    }
}

func (m *SLOMonitor) RegisterSLO(name string, target float64, period time.Duration) {
    m.mu.Lock()
    defer m.mu.Unlock()

    m.configs[name] = &SLOConfig{
        Name:          name,
        TargetPercent: target,
        Period:        period,
    }
    m.budgets[name] = NewErrorBudget(target, period)
}

func (m *SLOMonitor) RecordRequest(sloName string, success bool) {
    m.mu.RLock()
    budget, exists := m.budgets[sloName]
    m.mu.RUnlock()

    if exists {
        budget.RecordRequest(success)
    }
}

func (m *SLOMonitor) GetStatus(sloName string) SLOStatus {
    m.mu.RLock()
    defer m.mu.RUnlock()

    config := m.configs[sloName]
    budget := m.budgets[sloName]

    return SLOStatus{
        Name:           sloName,
        Target:         config.TargetPercent,
        Current:        budget.Availability(),
        BudgetRemaining: budget.BudgetRemaining(),
        BurnRate:       budget.BurnRate(),
        TimeToExhaust:  budget.TimeToExhaust(),
    }
}

type SLOStatus struct {
    Name            string
    Target          float64
    Current         float64
    BudgetRemaining float64
    BurnRate        float64
    TimeToExhaust   time.Duration
}

func (m *SLOMonitor) RunAlertChecks(ctx context.Context) <-chan Alert {
    alerts := make(chan Alert)

    go func() {
        ticker := time.NewTicker(1 * time.Minute)
        defer ticker.Stop()
        defer close(alerts)

        for {
            select {
            case <-ctx.Done():
                return
            case <-ticker.C:
                m.mu.RLock()
                for name, budget := range m.budgets {
                    burnRate := budget.BurnRate()
                    remaining := budget.BudgetRemaining()

                    if burnRate > 10 {
                        alerts <- Alert{
                            SLO:      name,
                            Severity: SeverityCritical,
                            Message:  fmt.Sprintf("%s: Burning budget at %.1fx", name, burnRate),
                            BudgetRemaining: remaining,
                        }
                    } else if burnRate > 2 {
                        alerts <- Alert{
                            SLO:      name,
                            Severity: SeverityWarning,
                            Message:  fmt.Sprintf("%s: Elevated burn rate %.1fx", name, burnRate),
                            BudgetRemaining: remaining,
                        }
                    } else if remaining < 10 {
                        alerts <- Alert{
                            SLO:      name,
                            Severity: SeverityWarning,
                            Message:  fmt.Sprintf("%s: %.1f%% budget remaining", name, remaining),
                            BudgetRemaining: remaining,
                        }
                    }
                }
                m.mu.RUnlock()
            }
        }
    }()

    return alerts
}

type Alert struct {
    SLO             string
    Severity        Severity
    Message         string
    BudgetRemaining float64
}

type Severity int

const (
    SeverityInfo Severity = iota
    SeverityWarning
    SeverityCritical
)
```

---

## 4. Alerting Implementation

### Alert Evaluator

```go
package alerting

import (
    "context"
    "time"
)

type AlertRule struct {
    Name      string
    Query     AlertQuery
    For       time.Duration
    Severity  Severity
    Labels    map[string]string
    Annotations map[string]string
}

type AlertQuery interface {
    Evaluate(ctx context.Context) (float64, error)
}

type ThresholdQuery struct {
    MetricName string
    Comparator string
    Threshold  float64
}

func (q *ThresholdQuery) Evaluate(ctx context.Context) (float64, error) {
    // Query Prometheus
    // This would use prometheus client
    return 0, nil
}

type AlertEvaluator struct {
    rules   []AlertRule
    history map[string][]timeSeriesSample
}

type timeSeriesSample struct {
    Timestamp time.Time
    Value     float64
}

func NewAlertEvaluator() *AlertEvaluator {
    return &AlertEvaluator{
        rules:   make([]AlertRule, 0),
        history: make(map[string][]timeSeriesSample),
    }
}

func (e *AlertEvaluator) AddRule(rule AlertRule) {
    e.rules = append(e.rules, rule)
    e.history[rule.Name] = make([]timeSeriesSample, 0)
}

func (e *AlertEvaluator) Evaluate(ctx context.Context) []FiringAlert {
    var firing []FiringAlert

    for _, rule := range e.rules {
        value, err := rule.Query.Evaluate(ctx)
        if err != nil {
            continue
        }

        // Store sample
        e.history[rule.Name] = append(e.history[rule.Name], timeSeriesSample{
            Timestamp: time.Now(),
            Value:     value,
        })

        // Check if condition met for required duration
        if e.shouldFire(rule.Name, rule.For) {
            firing = append(firing, FiringAlert{
                Name:       rule.Name,
                Value:      value,
                Severity:   rule.Severity,
                Labels:     rule.Labels,
                Annotations: rule.Annotations,
                FiredAt:    time.Now(),
            })
        }
    }

    return firing
}

func (e *AlertEvaluator) shouldFire(ruleName string, forDuration time.Duration) bool {
    samples := e.history[ruleName]
    if len(samples) == 0 {
        return false
    }

    // Check if condition has been true for the required duration
    now := time.Now()
    cutoff := now.Add(-forDuration)

    for _, sample := range samples {
        if sample.Timestamp.Before(cutoff) {
            // Remove old samples
            continue
        }
        // Check if condition was met
        // This depends on the specific query logic
    }

    return true
}

type FiringAlert struct {
    Name        string
    Value       float64
    Severity    Severity
    Labels      map[string]string
    Annotations map[string]string
    FiredAt     time.Time
}
```

---

## 5. Dashboard Queries

### Grafana Dashboard JSON (Key Panels)

```json
{
  "panels": [
    {
      "title": "Request Rate (RED - Rate)",
      "targets": [
        {
          "expr": "sum(rate(http_requests_total{service=\"$service\"}[5m])) by (endpoint)"
        }
      ]
    },
    {
      "title": "Error Rate (RED - Errors)",
      "targets": [
        {
          "expr": "sum(rate(http_errors_total{service=\"$service\"}[5m])) by (error_type)"
        }
      ]
    },
    {
      "title": "Latency (RED - Duration)",
      "targets": [
        {
          "expr": "histogram_quantile(0.50, sum(rate(http_duration_seconds_bucket{service=\"$service\"}[5m])) by (le, endpoint))",
          "legendFormat": "p50"
        },
        {
          "expr": "histogram_quantile(0.95, sum(rate(http_duration_seconds_bucket{service=\"$service\"}[5m])) by (le, endpoint))",
          "legendFormat": "p95"
        },
        {
          "expr": "histogram_quantile(0.99, sum(rate(http_duration_seconds_bucket{service=\"$service\"}[5m])) by (le, endpoint))",
          "legendFormat": "p99"
        }
      ]
    },
    {
      "title": "SLO - Availability",
      "targets": [
        {
          "expr": "(1 - sum(rate(http_errors_total{service=\"$service\"}[5m])) / sum(rate(http_requests_total{service=\"$service\"}[5m]))) * 100"
        }
      ],
      "alert": {
        "conditions": [
          {
            "evaluator": {
              "params": [99.9],
              "type": "lt"
            },
            "operator": {
              "type": "and"
            }
          }
        ]
      }
    },
    {
      "title": "Error Budget Remaining",
      "targets": [
        {
          "expr": "slo_budget_remaining{service=\"$service\"}"
        }
      ]
    }
  ]
}
```

---

## Summary

| Component | Implementation | Key Points |
|-----------|----------------|------------|
| **Tracing** | OpenTelemetry + Jaeger | Propagate context, record errors |
| **Logging** | Structured + trace IDs | Correlate logs with traces |
| **Metrics** | RED + USE methods | Control cardinality, use histograms |
| **SLOs** | Error budget tracking | Alert on burn rate, not thresholds |
| **Alerting** | Multi-condition | Symptom-based, SLO-driven |
| **Dashboards** | Grafana | SLI panels, error budget visualization |

---

**Best Practices:**

1. **Start simple**: Metrics first, then logs, then traces
2. **Cardinality budget**: Track unique label combinations
3. **SLOs drive everything**: Alert on SLO burn, not raw metrics
4. **Correlation is key**: trace IDs in logs, logs in traces
5. **Review regularly**: SLOs, alerts, and dashboards need tuning
