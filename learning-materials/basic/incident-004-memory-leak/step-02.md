# Step 02: Monitoring and Prevention

---

## Question 4: What Monitoring Would Have Caught This?

### In Staging

**1. Memory profiling before deploying:**

```javascript
// Add to staging deployment
const v8 = require('v8');

setInterval(() => {
  const usage = process.memoryUsage();
  const heapStats = v8.getHeapStatistics();

  console.log({
    heapUsed: `${Math.round(usage.heapUsed / 1024 / 1024)}MB`,
    heapTotal: `${Math.round(usage.heapTotal / 1024 / 1024)}MB`,
    external: `${Math.round(usage.external / 1024 / 1024)}MB`,
    heapSizeLimit: `${Math.round(heapStats.heap_size_limit / 1024 / 1024)}MB`
  });
}, 30000); // Every 30 seconds
```

**2. Load test with memory monitoring:**

```bash
# Run load test in staging
ab -n 10000 -c 100 http://staging.example.com/api/payments

# Watch memory usage
kubectl top pod -l app=payment-service --containers
```

**3. Heap snapshot on suspicion:**

```javascript
// Add endpoint for heap snapshot (STAGING ONLY!)
app.get('/debug/heap-snapshot', (req, res) => {
  const fs = require('fs');
  const fileName = `/tmp/heap-${Date.now()}.heapsnapshot`;
  v8.writeHeapSnapshot(fileName);
  res.json({ snapshot: fileName });
});

// Then analyze with Chrome DevTools
```

---

### Production Monitoring

**1. Prometheus metrics:**

```javascript
const promClient = require('prom-client');

const heapUsedGauge = new promClient.Gauge({
  name: 'node_heap_used_bytes',
  help: 'Process heap used bytes'
});

const heapTotalGauge = new promClient.Gauge({
  name: 'node_heap_total_bytes',
  help: 'Process heap total bytes'
});

setInterval(() => {
  const usage = process.memoryUsage();
  heapUsedGauge.set(usage.heapUsed);
  heapTotalGauge.set(usage.heapTotal);
}, 10000);
```

**2. Alert on memory growth rate:**

```yaml
# Prometheus alert
groups:
  - name: memory
    rules:
      - alert: MemoryLeakDetected
        expr: rate(node_heap_used_bytes[5m]) > 1000000  # Growing > 1MB/sec
        for: 10m
        annotations:
          summary: "Possible memory leak in {{ $labels.pod }}"
```

**3. Pre-deployment checklist:**

- [ ] Load test with 10x expected traffic
- [ ] Monitor memory during load test
- [ ] Check for memory growth over 1 hour
- [ ] Profile with Chrome DevTools
- [ ] Review object allocation patterns

---

## Prevention: Code Review Checklist

When reviewing code that creates objects:

**1. Is a collection created inside a loop?**
```javascript
// BAD
for (let i = 0; i < 1000000; i++) {
  const set = new Set();  // ← 1M Sets!
}

// GOOD
const set = new Set();
for (let i = 0; i < 1000000; i++) {
  set.add(i);
}
```

**2. Are closures holding references?**
```javascript
// BAD - Handler holds reference to largeData
function createHandler(largeData) {
  return function() {
    console.log('ready');
    // largeData is kept in memory even though unused!
  };
}

// GOOD
function createHandler() {
  return function() {
    console.log('ready');
  };
}
```

**3. Are event listeners added but never removed?**
```javascript
// BAD
emitter.on('data', handleData);  // Added every request, never removed

// GOOD - Use once() or removeListener()
emitter.once('data', handleData);
```

---

## Summary

| Issue | Fix |
|-------|-----|
| Creating Sets in hot path | Don't create - use array.includes() or Redis sets |
| No staging load test | Add load test with memory monitoring |
| No production alerts | Add Prometheus metrics + alerts |
| Post-deployment review | Code review checklist for object creation |

---

**Now read `solution.md` for complete reference.**
