---
name: obs-104-alert-fatigue
description: Alert Fatigue
difficulty: Intermediate
category: Observability / Alerting / On-Call
level: Senior Engineer
---
# Observability 104: Alert Fatigue

---

## The Situation

You're the on-call engineer. Your PagerDuty goes off constantly. Team is exhausted.

**Your alert rules:**

```yaml
groups:
  - name: everything
    rules:
      - alert: HighCPU
        expr: cpu_usage_percent > 50
        for: 1m

      - alert: LowDisk
        expr: disk_free_percent < 20
        for: 1m

      - alert: HighMemory
        expr: memory_usage_percent > 70
        for: 1m

      - alert: PodNotReady
        expr: kube_pod_status_ready == 0
        for: 1m

      - alert: RequestLatency
        expr: http_request_duration_seconds > 0.1
        for: 1m

      - alert: ErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0
        for: 1m
      # ... 50 more alerts
```

---

## The Incident

```
Week 1: 500+ alerts
Week 2: Team starts ignoring "minor" alerts
Week 3: Critical alert ignored ("just another CPU alert")
Week 4: Production outage, 30-minute response time

Postmortem finding:
- 95% of alerts were noise
- Team developed alert blindness
- Real issue masked by noise

Example noisy alert:
  "CPU > 50%" on development server
  Fires daily during tests, but no action needed
```

---

## The Jargon

| Term | Definition |
|------|------------|
| **Alert Fatigue** | Desensitization from too many alerts |
| **Page** | Urgent notification (PagerDuty, SMS) |
| **Ticket** | Non-urgent work item (Jira, email) |
| **Signal** | Meaningful alert requiring action |
| **Noise** | Alert without actionable response |
| **Threshold** | Value triggering alert |
| **For duration** | Time condition must be true |
| **Severity** | Alert importance (critical, warning, info) |
| **Escalation** | Sending alert to next person if no response |
| **Runbook** | Documented response procedures |

---

## The Problems

**1. Thresholds too low:**
```
CPU > 50%: Normal for busy servers
Memory > 70%: Linux cache usage
```

**2. No differentiation:**
```
Dev server gets same priority as prod
Temporary spikes treated same as sustained issues
```

**3. Actionability missing:**
```
"High CPU" → but what to do?
"Error rate > 0" → single error in 1M requests
```

**4. For duration too short:**
```
for: 1m → every blip triggers alert
```

---

## Questions

1. **What causes alert fatigue?**

2. **How do you distinguish signal from noise?**

3. **What makes an alert actionable?**

4. **How should severity levels be assigned?**

5. **As a Senior Engineer, how do you design an effective alerting strategy?**

---

**Read `step-01.md`**
