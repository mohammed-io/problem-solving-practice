# Step 03: Why Alerts Fail

---

## The Problem

The on-call team gets **20+ pages per night**. Most are false alarms.

```
Current alerts:
┌─────────────────────────────────────────────────────────────┐
│ ALERT: cpu_usage_high                                      │
│ Condition: cpu > 80%                                       │
│                                                             │
│ Fires: Every night at 3am (during batch jobs)              │
│ Action: "Check CPU" (but what can you do?)                 │
│ Result: Team starts ignoring ALL alerts                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Question: What Makes a Bad Alert?

Think about this alert: `cpu > 80%`

**Why is it bad?**

1. **It's a symptom, not a problem.**
   - High CPU might be normal during load
   - What are you supposed to do? "Reduce CPU" isn't actionable.

2. **It doesn't indicate user impact.**
   - CPU at 85% but all requests succeeding = no problem
   - CPU at 50% but errors spiking = real problem

3. **It's too sensitive.**
   - Brief spikes trigger it
   - No sustained threshold

4. **No context.**
   - Which service? Which endpoint?
   - Is this during a deployment?

---

## Good Alert vs Bad Alert

```
┌─────────────────────────────────────────────────────────────┐
│ BAD ALERT                                                   │
├─────────────────────────────────────────────────────────────┤
│ Name: cpu_usage_high                                        │
│ Condition: cpu > 80%                                        │
│ Fires: Daily                                               │
│ Action: ??? (What can you do?)                             │
│ Impact: Unknown                                            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ GOOD ALERT                                                  │
├─────────────────────────────────────────────────────────────┤
│ Name: high_error_rate_impacting_users                       │
│ Condition:                                                  │
│   - error_rate > 1%                                        │
│   - AND duration > 5 minutes                               │
│   - AND requests_per_second > 100                          │
│ Fires: Monthly (only real issues)                          │
│ Action: Rollback deployment, scale up, investigate         │
│ Impact: 1000+ users affected                                │
│ Runbook: https://runbooks.dev/high-error-rate              │
└─────────────────────────────────────────────────────────────┘
```

---

## The Golden Rule

**Alert on symptoms, not causes.**

| Alert Type | Example | Should Page? |
|------------|---------|--------------|
| **Symptom** | "Users can't checkout" | ✅ Yes |
| **Symptom** | "p95 latency > 500ms SLO breach" | ✅ Yes |
| **Cause** | "CPU > 80%" | ❌ No |
| **Cause** | "Database slow" | ❌ No |
| **Cause** | "Disk 90% full" | ❌ No (create ticket instead) |

**Why?** Causes don't always matter. Symptoms always matter.

---

## Quick Check

Before moving on, make sure you understand:

1. Why is `cpu > 80%` a bad alert? (Not actionable, no user impact)
2. What's the golden rule of alerting? (Alert on symptoms, not causes)
3. What makes an alert actionable? (Has clear action, known impact)

---

**Ready to learn multi-condition alerting? Read `step-04.md`**
