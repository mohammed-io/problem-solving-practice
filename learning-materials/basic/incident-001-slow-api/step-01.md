# Step 01

---

## Framework Selection

Before diving into details, pick a **systematic approach**.

For API performance issues, the **RED Method** is your friend:

| Letter | Metric | Question |
|--------|--------|----------|
| **R** | Rate | Is traffic normal? |
| **E** | Errors | Are errors elevated? |
| **D** | Duration | Is latency high? |

---

## What You Know

From the dashboard:

- **Rate**: ~500 req/s (normal) ✓
- **Errors**: 0.1% (normal) ✓
- **Duration**: p95 is **23x higher** than normal ✗

---

## What This Tells You

- The system isn't overwhelmed by traffic
- The system isn't throwing errors
- **Something is making requests take longer**

---

## Your Next Question

Given that the request rate is normal but latency is high...

**Where is the time being spent?**

Think about the request flow:
1. Client → API Service
2. API Service processes
3. API Service → Database
4. Database returns
5. API Service returns to client

Which step is slow?

---

**Still stuck? Read `step-02.md`**
