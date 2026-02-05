# Step 01: Breaking Down the User Schema

---

## Question 1: What Goes in the Users Table?

**Think about this:**
- Is profile data (avatar, bio) core to the "user" or could it be separate?
- How do you handle email vs phone signup?
- What about authentication (passwords, sessions)?

**Core user data:**
```sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE,  -- NULLable if phone signup
    phone VARCHAR(20) UNIQUE,   -- NULLable if email signup
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL, -- bcrypt/argon2
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,      -- Soft delete (GDPR)
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    suspended BOOLEAN NOT NULL DEFAULT FALSE
);
```

**Why separate profiles?**
- Profile data (avatar, bio) is read-heavy, updated rarely
- User data (email, password) is security-critical
- Separation allows different access patterns

```sql
CREATE TABLE user_profiles (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    display_name VARCHAR(100),
    avatar_url TEXT,
    bio TEXT,
    location VARCHAR(100),
    website TEXT
);
```

---

## Question 2: Username Uniqueness at Scale

**Problem:** With 10M users, how do you check if username is taken?

**Naive approach:**
```sql
-- This requires checking all rows (or index)
SELECT 1 FROM users WHERE username = 'cooluser';
```

**Better approach: Use the UNIQUE constraint's index**
```sql
-- The UNIQUE constraint creates a unique index
CREATE UNIQUE INDEX idx_users_username ON users(username);

-- Check becomes index lookup (O(log n))
INSERT INTO users (username, ...) VALUES ('cooluser', ...);
-- If duplicate, returns error
```

**For availability checks (API endpoint):**
```sql
-- Fast: Check if exists
SELECT EXISTS(SELECT 1 FROM users WHERE username = 'cooluser');
```

**For 10M+ usernames, consider:**
- Bloom filter for fast "probably exists" checks
- Reserved username list (admin, support, api)
- Username suggestions if taken

---

## Question 3: Where to Store Follower Relationships?

**Not in the users table!** That would require:
- Adding `followers` array to users (hard to query)
- Or adding `following` array (duplicate data)

**Solution: Separate relationship table (many-to-many)**
```sql
CREATE TABLE follows (
    follower_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    followee_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (follower_id, followee_id),
    CHECK (follower_id != followee_id)  -- Can't follow yourself
);

-- Index for common queries
CREATE INDEX idx_follows_follower ON follows(follower_id);
CREATE INDEX idx_follows_followee ON follows(followee_id);
```

**Query examples:**
```sql
-- Who follows user X?
SELECT follower_id FROM follows WHERE followee_id = ?;

-- Who is user X following?
SELECT followee_id FROM follows WHERE follower_id = ?;

-- How many followers?
SELECT COUNT(*) FROM follows WHERE followee_id = ?;
```

---

## Question 4: Email vs Phone Signup

**Both columns can be NULL:**
```sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(20) UNIQUE,
    -- At least one must be set (CHECK constraint)
    CHECK (email IS NOT NULL OR phone IS NOT NULL),
    ...
);
```

**User can have both:**
- Sign up with email, add phone later
- Sign up with phone, add email later
- Either way, they need a username

---

**Still thinking? Read `step-02.md`**

---

## Quick Check

Before moving on, make sure you understand:

1. Why separate users and user_profiles tables? (Security, different access patterns)
2. How does UNIQUE constraint help with availability checks? (Creates index, O(log n) lookup)
3. Why use a separate follows table instead of arrays? (Queryable, scalable, no duplicate data)
4. How do you handle both email and phone signup? (Both NULLable, CHECK for at least one)
5. What's the benefit of partial indexes? (Smaller index, faster lookups, less write overhead)

