# Design 001: Solution - User Schema

---

## Core Users Table

```sql
CREATE TABLE users (
  -- Primary key: never changes, internal ID
  id BIGSERIAL PRIMARY KEY,

  -- Authentication identifiers
  email VARCHAR(255),
  phone VARCHAR(20),

  -- Public profile
  username VARCHAR(30) NOT NULL,
  display_name VARCHAR(100),
  bio TEXT,
  avatar_url VARCHAR(512),
  location VARCHAR(100),

  -- Metadata
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Account state
  is_verified BOOLEAN NOT NULL DEFAULT FALSE,
  is_suspended BOOLEAN NOT NULL DEFAULT FALSE,
  suspended_at TIMESTAMPTZ,
  suspended_reason TEXT,

  -- Deletion (GDPR/CCPA compliance)
  deleted_at TIMESTAMPTZ,  -- NULL = active, NOT NULL = deleted

  -- Constraints
  CONSTRAINT email_unique UNIQUE (email) DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT phone_unique UNIQUE (phone) DEFERRABLE INITIALLY DEFERRED
) PARTITION BY RANGE (created_at);

-- Partial index for unique username (only active users)
CREATE UNIQUE INDEX users_username_unique
  ON users (username)
  WHERE deleted_at IS NULL;

-- Email lookup index (for login)
CREATE INDEX users_email_idx
  ON users (email)
  WHERE deleted_at IS NULL AND email IS NOT NULL;

-- Phone lookup index (for login)
CREATE INDEX users_phone_idx
  ON users (phone)
  WHERE deleted_at IS NULL AND phone IS NOT NULL;

-- Search index (for finding users by name)
CREATE INDEX users_display_name_trgm_idx
  ON users USING gin (display_name gin_trgm_ops)
  WHERE deleted_at IS NULL;
```

---

## Follows Table (Many-to-Many)

```sql
CREATE TABLE follows (
  -- Composite primary key (prevents duplicate follows)
  follower_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  following_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  PRIMARY KEY (follower_id, following_id),

  -- Prevent self-follows
  CONSTRAINT no_self_follow CHECK (follower_id != following_id),

  -- Index for "who follows X" (followers list)
  INDEX follows_following_idx (following_id, created_at DESC),

  -- Index for "who does X follow" (following list)
  INDEX follows_follower_idx (follower_id, created_at DESC)
);

-- Materialized view for follower counts (updated periodically)
CREATE MATERIALIZED VIEW follower_counts AS
SELECT
  following_id AS user_id,
  COUNT(*) AS follower_count
FROM follows
GROUP BY following_id;

CREATE UNIQUE INDEX follower_counts_user_id_idx ON follower_counts(user_id);

-- Index to quickly check if user follows another (for "follows you" feature)
CREATE INDEX follows_mutual_check_idx
  ON follows (follower_id, following_id)
  WHERE following_id IN (SELECT follower_id FROM follows);
```

---

## Blocking Table

```sql
CREATE TABLE blocks (
  blocker_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  blocked_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  PRIMARY KEY (blocker_id, blocked_id),

  -- Prevent self-blocks
  CONSTRAINT no_self_block CHECK (blocker_id != blocked_id)
);

-- Index for checking if blocked
CREATE INDEX blocks_blocker_idx ON blocks (blocker_id, blocked_id);
```

---

## Partitioning (For Scale)

```sql
-- Partition by year (makes vacuuming, archival easier)
CREATE TABLE users (
  -- ... same columns ...
) PARTITION BY RANGE (created_at);

-- Create partitions
CREATE TABLE users_2024 PARTITION OF users
  FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

CREATE TABLE users_2025 PARTITION OF users
  FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

-- Default partition for future data
CREATE TABLE users_future PARTITION OF users
  DEFAULT;
```

---

## Username Uniqueness at Scale

The problem: Checking username availability requires scanning the entire table.

### Approach 1: Pre-Generated Usernames

```sql
CREATE TABLE available_usernames (
  username VARCHAR(30) PRIMARY KEY,
  reserved_until TIMESTAMPTZ
);

-- Background job pre-generates millions of valid usernames
-- On signup, first check this table (fast lookup)
-- Then attempt to claim in users table
```

### Approach 2: Key-Value Store for Availability

Use Redis for availability checks (eventually consistent):
```javascript
async function isUsernameAvailable(username) {
  // Check Redis first (fast)
  const cached = await redis.get(`username:${username}`);
  if (cached === 'taken') return false;

  // Check Postgres (source of truth)
  const exists = await db.query(
    'SELECT 1 FROM users WHERE username = $1 AND deleted_at IS NULL', [username]
  );

  if (exists.rows[0]) {
    await redis.set(`username:${username}`, 'taken', 'EX', 3600);
    return false;
  }

  // Reserve in Redis while user completes signup
  await redis.set(`username:${username}`, 'reserved', 'EX', 300);
  return true;
}
```

---

## Key Design Decisions

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **BIGSERIAL for id** | Never exposed, internal only | Users can't guess IDs |
| **DEFERRABLE constraints** | Allows flexibility in bulk loads | Must remember to defer |
| **Partial index for username** | Soft deletes don't block usernames | Must include WHERE clause in queries |
| **Separate follows table** | Normalization, scales independently | Requires joins for queries |
| **Materialized view** | Fast follower count lookups | Not real-time, needs refresh |
| **Partitioning by created_at** | Easier archival, vacuuming | Queries need partition pruning |

---

## What This Doesn't Handle

At scale (10M+ users), you'd need:

1. **Read replicas** - Offload read queries to followers DB
2. **Caching layer** - Redis for user profile lookups
3. **Search service** - OpenSearch/Elasticsearch for user search
4. **Fanout service** - Async delivery of posts to followers

---

## Jargon

| Term | Definition |
|------|------------|
| **BIGSERIAL** | Auto-incrementing 64-bit integer (can create billions of IDs) |
| **DEFERRABLE constraint** | Constraint checked at transaction COMMIT, not immediately |
| **Partial index** | Index that only includes rows matching a WHERE clause (saves space) |
| **Materialized view** | Pre-computed query result stored as table (fast reads, needs refresh) |
| **Covering index** | Index containing all columns a query needs (avoids table lookup) |
| **GIN index** | Generalized Inverted Index (for arrays, full-text search, JSON) |
| **Trigram index** | Index for substring search (breaks string into 3-char chunks) |
| **Foreign Key CASCADE** | When referenced row is deleted, dependent rows are auto-deleted |
| **Soft delete** | Marking rows as deleted (deleted_at) instead of actually deleting them |
| **Partition pruning** | Query optimizer only scans relevant partitions based on WHERE clause |

---

**Next Problem:** `basic/design-002-message-queue/`
