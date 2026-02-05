# Step 01: The Idempotency Problem

---

## What is Idempotency?

**Mathematical definition:** f(f(x)) = f(x)

**In practice:** Applying the same operation multiple times produces the same result as applying it once.

---

## Idempotent vs Non-Idempotent

```
✅ IDEMPOTENT:
GET /users/123          → Returns user data
PUT /users/123 {name: X} → Sets name to X
DELETE /users/123       → Deletes user
Running multiple times = same result

❌ NOT IDEMPOTENT:
POST /payments {amount: 100}  → Charges $100 each time!
POST /orders {items: [...]}   → Creates duplicate orders
POST /counter {op: increment} → Increments multiple times
```

---

## The Real-World Problem

```
Scenario: Payment API

1. Client sends charge $100 request
   with Idempotency-Key: abc-123

2. Server processes payment, charges card

3. Network timeout! Client never receives response

4. Client retries with SAME Idempotency-Key: abc-123

5. Server should:
   ✅ Return cached response (same payment_id)
   ❌ Charge card again (double charge!)
```

---

## Why Idempotency Keys Matter

```
Without Idempotency:
- Network timeout → Client retries
- Result: Customer charged $200 instead of $100
- Support nightmare

With Idempotency:
- Network timeout → Client retries with same key
- Result: Server returns cached response
- Customer charged exactly $100
```

---

## The Challenge: Race Conditions

```
Time | Request A              | Request B
-----|------------------------|------------------------
T1   | Check key: not found  |
T2   |                       | Check key: not found
T3   | Process payment       | Process payment
T4   | Store result          | Store result
T5   | Return response       | Return response

Result: Charged TWICE!
```

**Both requests missed the cache check!**

---

## Quick Check

Before moving on, make sure you understand:

1. What is idempotency? (f(f(x)) = f(x), same result on repeat)
2. Which HTTP methods are idempotent? (GET, PUT, DELETE, HEAD)
3. Which are not idempotent? (POST, PATCH)
4. Why do we need idempotency keys? (Network timeouts, retries)
5. What's the race condition problem? (Parallel requests both miss cache)

---

**Ready to design the solution? Read `step-02.md`**
