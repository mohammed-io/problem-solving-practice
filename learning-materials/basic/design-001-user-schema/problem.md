---
name: design-001-user-schema
description: User Schema Design
difficulty: Basic
category: Database Design
level: Mid-level
---
# Design 001: User Schema Design

---

## The Situation

You're designing the user system for a new social media app, "Connectify".

The product manager gives you these requirements:

> "We need users who can:
> - Sign up with email or phone
> - Have a username (must be unique)
> - Have a profile with avatar, bio, location
> - Follow other users (like Twitter)
> - Have followers
> - Write posts (text + images)
> - Like posts
> - Comment on posts
> - Have a 'verified' badge
> - Search for other users
> - Block other users
> - Be in a 'suspended' state for violations"

Your database is **PostgreSQL 15**.

---

## Technical Constraints

- **Expected scale**: 10 million users in year 1
- **Read:Write ratio**: 100:1 (lots more reads than writes)
- **Geographic**: Global, but most users in North America
- **Compliance**: GDPR, CCPA (data retention, right to deletion)

---

## Questions for You

1. **How would you structure the users table?** What columns, data types, constraints?

2. **How do you handle username uniqueness at scale?** (10M users, checking availability)

3. **Where do you store follower relationships?** Is it part of users table?

4. **How do you handle email vs phone signup?** Can a user have both?

5. **What indexes do you need?** (Remember: indexes slow down writes)

---

## Jargon

| Term | Definition |
|------|------------|
| **Read:Write ratio** | Proportion of read operations to write operations; 100:1 means 100 reads for every 1 write |
| **Constraint** | Rule enforced by database (UNIQUE, NOT NULL, FOREIGN KEY) |
| **Index** | Data structure that speeds up reads but slows down writes |
| **Foreign Key** | Column referencing primary key in another table (enforces referential integrity) |
| **Normalization** | Organizing data to reduce redundancy (typically 3NF for transactional systems) |
| **Denormalization** | Duplicating data intentionally to improve read performance |
| **Partial index** | Index with a WHERE clause (only indexes some rows) |
| **Covering index** | Index containing all columns needed for a query (avoids table lookup) |

---

## Your Task

Design the schema. Consider:

1. **What goes in the users table?** (What's core user data vs. profile data?)

2. **How to handle uniqueness checks?** (Username uniqueness at scale is tricky)

3. **How to model follows/followers?** (Many-to-many relationship)

4. **What about soft deletes?** (User deletion compliance)

5. **How to handle "verified" status?** (Boolean? Separate table?)

Write your schema as SQL `CREATE TABLE` statements with indexes.

---

**When you have a design, read `step-01.md`**
