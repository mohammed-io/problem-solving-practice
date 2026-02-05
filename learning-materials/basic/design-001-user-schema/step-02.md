# Step 02: Completing the Schema

---

## Question 5: What Indexes Do You Need?

**Remember: Indexes speed up reads but slow down writes.**

**For 100:1 read:write ratio, add these indexes:**

```sql
-- Email lookup (login, uniqueness check)
CREATE INDEX idx_users_email ON users(email) WHERE email IS NOT NULL;

-- Phone lookup (login, uniqueness check)
CREATE INDEX idx_users_phone ON users(phone) WHERE phone IS NOT NULL;

-- Username lookup (already UNIQUE, creates index)
-- CREATE UNIQUE INDEX idx_users_username ON users(username);

-- Verified users (common filter)
CREATE INDEX idx_users_verified ON users(id) WHERE verified = TRUE;

-- Active users (not deleted, not suspended)
CREATE INDEX idx_users_active ON users(id)
WHERE deleted_at IS NULL AND suspended = FALSE;

-- Follower counts (analytics)
-- These are maintained by triggers or application logic
CREATE TABLE user_stats (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    followers_count INT NOT NULL DEFAULT 0,
    following_count INT NOT NULL DEFAULT 0,
    posts_count INT NOT NULL DEFAULT 0
);
```

**Partial indexes (with WHERE) save space:**
- Only index rows that match criteria
- Smaller index = faster lookups, less write overhead

---

## Posts, Likes, Comments

**Posts table:**
```sql
CREATE TABLE posts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_posts_user_created ON posts(user_id, created_at DESC);
CREATE INDEX idx_posts_created ON posts(created_at DESC) WHERE deleted_at IS NULL;
```

**Likes table:**
```sql
CREATE TABLE likes (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    post_id BIGINT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, post_id)
);

CREATE INDEX idx_likes_post ON likes(post_id);
```

**Comments table:**
```sql
CREATE TABLE comments (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    post_id BIGINT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    parent_id BIGINT REFERENCES comments(id) ON DELETE CASCADE,  -- For replies
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_comments_post ON comments(post_id, created_at);
```

---

## Blocking and Verification

**Blocks table:**
```sql
CREATE TABLE blocks (
    blocker_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blocked_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (blocker_id, blocked_id),
    CHECK (blocker_id != blocked_id)
);

-- Fast check: Is user blocking someone?
SELECT 1 FROM blocks WHERE blocker_id = ? AND blocked_id = ?;
```

**Verification:**
```sql
-- Simple approach: Boolean column
ALTER TABLE users ADD COLUMN verified BOOLEAN NOT NULL DEFAULT FALSE;

-- Better approach: Verification table (audit trail)
CREATE TABLE verifications (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_by BIGINT REFERENCES users(id),  -- Admin who verified
    method VARCHAR(50),  -- email, phone, manual
    notes TEXT
);
```

---

## GDPR Compliance: Right to Deletion

**Soft delete approach:**
```sql
ALTER TABLE users ADD COLUMN deleted_at TIMESTAMPTZ;

-- "Delete" actually anonymizes
UPDATE users SET
    email = 'deleted-' || id || '@deleted',
    phone = NULL,
    username = 'deleted-' || id,
    password_hash = '',
    deleted_at = NOW()
WHERE id = ?;

-- Hard delete after retention period (e.g., 30 days)
DELETE FROM users WHERE deleted_at < NOW() - INTERVAL '30 days';
```

---

## Complete Schema Summary

```
users              -- Core user data
├── user_profiles  -- Extended profile info
├── user_stats     -- Follower/post counts (denormalized)
├── verifications  -- Verification audit trail
├── posts          -- User posts
├── follows        -- Follower relationships (many-to-many)
├── blocks         -- Blocked users (many-to-many)
└── likes          -- Post likes (many-to-many)
    └── comments   -- Post comments (self-referencing)
```

**Design principles applied:**
1. **Normalization**: Each entity has its own table
2. **Denormalization**: `user_stats` for fast count queries
3. **Partial indexes**: Only index what you query
4. **Soft delete**: Compliance with data retention
5. **CASCADE delete**: Cleanup related data on deletion

---

**Now read `solution.md` for the complete reference schema.**

---

## Quick Check

Before moving on, make sure you understand:

1. What are partial indexes and why use them? (Index only matching rows, saves space)
2. How do you handle GDPR right to deletion? (Soft delete first, anonymize, hard delete later)
3. Why use a user_stats table? (Fast count queries without scanning follows table)
4. What's the cascade delete strategy? (CASCADE for user-owned data, RESTRICT for shared)
5. How do self-referencing foreign keys work? (comments.parent_id references comments.id)

