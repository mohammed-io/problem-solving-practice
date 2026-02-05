# Step 2: Complete Observability

---

## Distributed Tracing

```javascript
import * as trace from '@opentelemetry/api';
import { NodeTracerProvider } from '@opentelemetry/sdk-trace-node';
import { JaegerExporter } from '@opentelemetry/exporter-jaeger';

// Setup tracing
const provider = new NodeTracerProvider();
provider.register();

const exporter = new JaegerExporter({ serviceName: 'order-service' });
provider.addSpanProcessor(new SimpleSpanProcessor(exporter));

// In your code
const tracer = trace.getTracer('order-service');

async function createOrder(userId, items) {
  const span = tracer.startSpan('createOrder');
  span.setAttribute('user_id', userId);
  span.setAttribute('item_count', items.length);

  try {
    // Database call
    const dbSpan = tracer.startSpan('database.query', { parent: span });
    const order = await db.query('INSERT INTO orders ...', [userId, items]);
    dbSpan.end();

    // Cache update
    const cacheSpan = tracer.startSpan('cache.invalidate', { parent: span });
    await redis.del(`user:${userId}:orders`);
    cacheSpan.end();

    span.setStatus({ code: SpanStatusCode.OK });
    return order;
  } catch (error) {
    span.recordException(error);
    span.setStatus({ code: SpanStatusCode.ERROR, message: error.message });
    throw error;
  } finally {
    span.end();
  }
}
```

---

## Structured Logging

```javascript
import pino from 'pino';

const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  formatters: {
    level: (label) => ({ level: label }),
  },
});

// Instead of console.log
async function processOrder(orderId) {
  logger.info({ order_id: orderId }, 'Processing order');

  try {
    const result = await service.process(orderId);
    logger.info({ order_id: orderId, result }, 'Order processed');
  } catch (error) {
    logger.error({ order_id: orderId, error: error.message, stack: error.stack }, 'Order failed');
    throw error;
  }
}
```

**Log levels:**
- `error`: Service impact, requires attention
- `warn`: Something wrong but continuing
- `info`: Normal operation, key events
- `debug`: Detailed diagnostic info

---

## Metrics

```javascript
import { Prometheus } from '@opentelemetry/exporter-prometheus';
import { MeterProvider } from '@opentelemetry/sdk-metrics';

const meterProvider = new MeterProvider();
const meter = meterProvider.getMeter('order-service');

// Counter (monotonic, only increases)
const orderCounter = meter.createCounter('orders.total', {
  description: 'Total number of orders'
});

// Histogram (distributions)
const orderDuration = meter.createHistogram('order.duration', {
  description: 'Order processing duration',
  unit: 'ms'
});

// Gauge (up/down)
const activeOrders = meter.createGauge('orders.active', {
  description: 'Currently processing orders'
});

// In your code
async function createOrder(userId, items) {
  const startTime = Date.now();
  activeOrders.add(1, { user_id: userId });

  try {
    const result = await processOrder(userId, items);
    orderCounter.add(1, { status: 'success' });
    return result;
  } catch (error) {
    orderCounter.add(1, { status: 'failed' });
    throw error;
  } finally {
    const duration = Date.now() - startTime;
    orderDuration.record(duration, { user_id: userId });
    activeOrders.add(-1, { user_id: userId });
  }
}
```

---

## SLOs and Alerting

```yaml
# SLO Definition
slo:
  name: "API Latency"
  target: "99.9% of requests < 100ms"
  rolling_window: "30 days"

# Alert on SLO breach, not metrics
alerts:
  - name: HighLatency
    condition: slo_error_rate > 0.01  # > 1% of requests over SLO
    for: 5m
    severity: critical
    action: page_on_call

  - name: HighErrorRate
    condition: http_requests_total{status=~"5.."} / http_requests_total > 0.05  # > 5% errors
    for: 2m
    severity: critical
    action: page_on_call

  - name: HighLatencyWarning
    condition: slo_error_rate > 0.001  # > 0.1% over SLO
    for: 15m
    severity: warning
    action: create_ticket
```

---

## Observability Stack

```
┌─────────────────────────────────────────────────────────┐
│                      Application                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐│
│  │ Tracing  │  │ Metrics  │  │ Logging  │  │  SLOs    ││
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘│
└───────┼────────────┼────────────┼────────────┼─────────┘
        │            │            │            │
        ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────────┐
│                   OpenTelemetry Collector               │
│         (Ingests all signals, exports to backends)      │
└────┬───────────────┬────────────────┬───────────┬──────┘
     │               │                │           │
     ▼               ▼                ▼           ▼
┌─────────┐   ┌──────────┐   ┌──────────┐  ┌──────────┐
│ Jaeger  │   │Prometheus│   │ Loki /   │  │  Grafana │
│(Traces) │   │(Metrics) │   │ Elastic  │  │(Dashboards│
└─────────┘   └──────────┘   │(Logs)    │  │  & Alert)│
                              └──────────┘  └──────────┘
```

---

## Dashboard Template

```yaml
# Grafana dashboard panels
panels:
  - title: Request Rate
    query: rate(http_requests_total[1m])
    type: graph

  - title: P50, P95, P99 Latency
    query: histogram_quantile(0.50, http_duration_seconds) ...
    type: graph

  - title: Error Rate
    query: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])
    type: graph

  - title: SLO Status (Latency)
    query: |
      1 - (
        sum(rate(http_duration_seconds_bucket{le="0.1"}[5m])) /
        sum(rate(http_duration_seconds_count[5m]))
      )
    type: stat

  - title: Active Traces
    query: jaeger_traces_count
    type: stat
```

---

**Now read `solution.md` for complete reference.**
