---
name: des-001-api-design
description: System design problem
difficulty: Advanced
category: Design Review / API / Staff Engineer
level: Staff Engineer
---
# Design Review 001: API Design Review

---

## The Design Document

**Author:** Junior engineer proposing new API

```
# User Profile API

## Overview
REST API for managing user profiles

## Endpoints

GET /api/users/:id
  Returns: Full user profile
  Includes: name, email, preferences, history, stats

POST /api/users/:id
  Updates: User profile
  Body: Any fields from profile

GET /api/users
  Returns: All users (for admin)
  No pagination (we don't have many users)

Authentication: API key in header
Rate limiting: 1000 requests/hour per user
```

---

## Your Role

You're reviewing this design as a Staff Engineer. Identify issues before implementation.

---

## Questions to Consider

1. **Security**: Is exposing user emails appropriate?

2. **Privacy**: GDPR compliance for personal data?

3. **Performance**: "All users" without pagination?

4. **Idempotency**: What if POST is called twice?

5. **Versioning**: How to handle breaking changes?

6. **Error handling**: What errors can occur?

---

**Read `step-01.md` for analysis
