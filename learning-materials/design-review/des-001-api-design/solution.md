# Solution: API Design Review

---

## Design Review Checklist

**Before approving any API:**

**Security:**
- [ ] No PII in public endpoints
- [ ] Proper authentication (not API keys)
- [ ] Rate limiting per user/resource
- [ ] Input validation on all fields

**Performance:**
- [ ] Pagination on list endpoints
- [ ] Field selection (partial response)
- [ ] Caching strategy defined
- [ ] N+1 query prevention

**Reliability:**
- [ ] Idempotent operations
- [ ] Timeout handling
- [ ] Circuit breakers for dependencies
- [ ] Graceful degradation

**Evolution:**
- [ ] Versioning strategy
- [ ] Deprecation process
- [ ] Backward compatibility
- [ ] Migration path

---

## Key Takeaways

**As a Staff/Principal engineer:**
- Think about 10x scale, not just current
- Security by design, not bolted on
- Plan for evolution from day 1
- Default to safe patterns (pagination, idempotency)

---

**Next Problem:** `design-review/des-002-data-model/`
