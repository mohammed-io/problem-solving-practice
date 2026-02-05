# Step 05: Choosing Between Choreography and Orchestration

---

## The Dilemma

You need to implement a saga. Which approach do you choose?

```
Choreography vs Orchestration:

┌─────────────────────────────────────────────────────────────┐
│                    CHOREOGRAPHY                             │
│  ┌──────────┐    events    ┌──────────┐    events    ┌───┐  │
│  │  Order   │────────────▶│ Payment  │────────────▶│Inv│  │
│  │ Service  │             │ Service  │             │Svc│  │
│  └──────────┘             └──────────┘             └───┘  │
│                                                             │
│  No coordinator, events flow between services             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     ORCHESTRATION                            │
│                                                             │
│                    ┌───────────┐                            │
│                    │Orchestrator│                            │
│                    │  (Directs)  │                            │
│                    └─────┬───────┘                            │
│             ┌───────────────┼───────────────┐                │
│             ▼               ▼               ▼                │
│        ┌─────────┐    ┌─────────┐    ┌─────────┐           │
│        │  Order  │    │ Payment  │    │Inventory│           │
│        │ Service │    │ Service │    │ Service │           │
│        └─────────┘    └─────────┘    └─────────┘           │
│                                                             │
│  Central coordinator directs all services                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Decision Framework

Use this decision tree:

```
Start
 │
 ├─ Is the workflow simple (2-3 steps)?
 │   └─ YES → Consider Choreography
 │   └─ NO  → Go to next question
 │
 ├─ Do different teams own each service?
 │   └─ YES → Consider Choreography (autonomy)
 │   └─ NO  → Go to next question
 │
 ├─ Is the workflow business-critical (money, compliance)?
 │   └─ YES → Use Orchestration (audit trail, control)
 │   └─ NO  → Go to next question
 │
 ├─ Do you need complex compensation logic?
 │   └─ YES → Use Orchestration (easier to manage)
 │   └─ NO  → Go to next question
 │
 └─ Do you need high availability (no SPOF)?
     └─ YES → Consider Choreography
     └─ NO  → Use Orchestration (with HA setup)
```

---

## Comparison Matrix

| Aspect | Choreography | Orchestration |
|--------|-------------|---------------|
| **Complexity** | Best for simple (2-3 steps) | Best for complex (5+ steps) |
| **Ownership** | Independent teams | Central team owns orchestrator |
| **Debugging** | Hard (distributed logic) | Easy (central state) |
| **Visibility** | Events scatter everywhere | Single place to see state |
| **Reliability** | No SPOF | Orchestrator is SPOF |
| **Coupling** | Loose (via events) | Tight (orchestrator knows all) |
| **Modification** | Add subscriber | Change orchestrator |
| **Startup cost** | Low (just emit events) | Higher (build orchestrator) |

---

## Real-World Examples

**Netflix (Choreography):**
- Thousands of microservices
- Teams are independent
- Event-driven architecture (Kafka)
- Uses choreography for most flows

**Amazon (Orchestration):**
- Order fulfillment is complex (10+ steps)
- Business-critical (money transactions)
- Needs audit trails
- Uses orchestration for order flows

**Uber (Mixed):**
- Choreography for simple notifications
- Orchestration for complex booking flows
- Event-driven architecture with some central coordination

---

## Hybrid Approach

You can combine both:

```
┌─────────────────────────────────────────────────────────────┐
│                    HYBRID APPROACH                          │
│                                                             │
│  High-Level Flow: Orchestration                             │
│  ┌─────────────────────────────────────────────┐           │
│  │  Orchestrator coordinates major steps       │           │
│  └─────────────────────────────────────────────┘           │
│          │                  │                             │
│          ▼                  ▼                             │
│  ┌─────────────┐    ┌─────────────┐                       │
│  │   Order     │    │  Payment    │                       │
│  │   Service   │    │  Service    │                       │
│  │             │    │             │                       │
│  │  Internal:  │    │  Internal:  │                       │
│  │  Choreography│    │  Orchestra- │                       │
│  │  (multiple  │    │  ted        │                       │
│  │   steps)    │    │             │                       │
│  └─────────────┘    └─────────────┘                       │
│                                                             │
│  Rule: Use orchestration for cross-service boundaries      │
│        Use choreography for internal service steps         │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Check

Before moving on, make sure you understand:

1. When to use choreography? (Simple flows, independent teams)
2. When to use orchestration? (Complex flows, business-critical)
3. Can you mix them? (Yes, orchestration for boundaries, choreography internally)
4. What's the key tradeoff? (SPOF vs. complexity)

---

**Ready to learn about failure handling? Read `step-06.md`**
