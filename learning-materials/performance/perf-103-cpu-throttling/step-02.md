# Step 2: Solutions

---

## Option 1: Increase Limit

```yaml
resources:
  requests:
    cpu: 2000m
  limits:
    cpu: 4000m  # Allow bursting
```

---

## Option 2: Remove Limits

```yaml
resources:
  requests:
    cpu: 2000m
  # No limit = can use all available CPU
  # Risk: Noisy neighbor
```

---

## Option 3: Use Burstable QoS

```yaml
# Burstable: request < limit
# Guaranteed: request == limit
# BestEffort: no request

resources:
  requests:
    cpu: 500m    # Guaranteed
  limits:
    cpu: 4000m   # Can burst
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's the simplest solution? (Increase CPU limit to allow bursting)
2. What's the risk of removing CPU limits? (Noisy neighbor - can starve other pods)
3. What's QoS class? (Quality of Service: Guaranteed, Burstable, BestEffort based on requests/limits)
4. What's Burstable QoS? (request < limit - gets guaranteed CPU but can burst)
5. What's the trade-off with higher limits? (More resources reserved but no throttling)

---

**Read `solution.md`
