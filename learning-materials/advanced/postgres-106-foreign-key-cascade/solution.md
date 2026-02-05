# Solution: Foreign Key Cascade - Explicit Deletion Policies

---

## Root Cause

**CASCADE can destroy other users' data** when relationships form a network, not just a tree.

---

## Complete Solution

### Solution 1: Cascade Audit Tool

```sql
-- Query to visualize cascade relationships
WITH RECURSIVE cascade_graph AS (
    -- Starting table
    SELECT
        'users'::text AS table_name,
        'user_id'::text AS fk_column,
        conname AS constraint_name,
        confdeltype AS on_delete,
        ARRAY['posts']::text[] AS cascade_path
    FROM pg_constraint
    WHERE conrelid = 'users'::regclass

    UNION ALL

    -- Recursive: follow FKs
    SELECT
        cl.confrelid::regclass::text AS table_name,
        a2.attname::text AS fk_column,
        cl.conname AS constraint_name,
        cl.confdeltype AS on_delete,
        cg.cascade_path || cl.confrelid::regclass::text
    FROM pg_constraint cl
    JOIN pg_attribute a1 ON a1.attnum = cl.conkey[1] AND a1.attrelid = cl.conrelid
    JOIN pg_attribute a2 ON a2.attnum = cl.confkey[1] AND a2.attrelid = cl.confrelid
    JOIN cascade_graph cg ON a1.attname = ANY(cg.cascade_path)
    WHERE cl.contype = 'f'
      AND cl.confdeltype = 'c'  -- CASCADE
)
SELECT * FROM cascade_graph;
```

### Solution 2: Soft Delete (Recommended)

```sql
-- Add soft delete columns
ALTER TABLE users ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN deleted_by INT REFERENCES users(id);

-- Create view for active users
CREATE VIEW active_users AS
SELECT * FROM users WHERE deleted_at IS NULL;

-- Index for filtering
CREATE INDEX idx_users_deleted_at ON users(deleted_at) WHERE deleted_at IS NULL;

-- Application uses view
SELECT * FROM active_users WHERE id = 123;
```

**Benefits:**
- No data loss
- Can be undone
- Auditable (deleted_by, deleted_at)
- CASCADE never happens

### Solution 3: Explicit Application-Level Cascade

```sql
-- Remove CASCADE, add NO ACTION
ALTER TABLE comments
DROP CONSTRAINT IF EXISTS comments_user_id_fkey,
ADD CONSTRAINT comments_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE NO ACTION;

ALTER TABLE posts
DROP CONSTRAINT IF EXISTS posts_user_id_fkey,
ADD CONSTRAINT posts_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE NO ACTION;
```

```python
class UserService:
    def delete_user(self, user_id):
        # Analyze impact
        impact = self.db.query("""
            WITH RECURSIVE cascade_tree AS (
                SELECT 'users' as table_name, id as ref_id
                UNION ALL
                SELECT
                    cl.confrelid::regclass::text,
                    c.ref_id
                FROM cascade_tree c
                JOIN pg_constraint cl ON cl.conrelid = c.table_name::regclass
                WHERE cl.contype = 'f' AND cl.confdeltype = 'c'
            )
            SELECT table_name, COUNT(*) as row_count
            FROM cascade_tree
            JOIN %s ON %s.id = cascade_tree.ref_id
            GROUP BY table_name
        """ % (self.table, self.table))

        # Show impact to user
        if impact['posts'] > 0:
            log.info(f"Will delete {impact['posts']} posts")

        # Execute with explicit confirmation
        confirmed = self.confirm_deletion(impact)
        if not confirmed:
            return False

        # Delete in dependency order
        self.db.execute("DELETE FROM comments WHERE user_id = %s", user_id)
        self.db.execute("DELETE FROM posts WHERE user_id = %s", user_id)
        self.db.execute("DELETE FROM users WHERE id = %s", user_id)

        return True
```

### Solution 4: Archival Before Deletion

```sql
-- Archive to separate table
CREATE TABLE deleted_users (
    LIKE users INCLUDING ALL
);

-- Before delete, archive
INSERT INTO deleted_users
SELECT * FROM users WHERE id = 123;

-- Now safe to delete
DELETE FROM users WHERE id = 123;
```

---

## Design Guidelines

### Rule 1: Avoid CASCADE on User-Generated Content

```
Bad: comments.user_id → users.id CASCADE
Good: comments.user_id → users.id NO ACTION

Reason: Deleting user shouldn't destroy others' content
```

### Rule 2: CASCADE Only for Owned Relationships

```
OK: posts.user_id → users.id CASCADE
    (User's posts, safe to delete)

NOT OK: comments.post_id → posts.id CASCADE
     (Others' comments on post, unsafe)
```

### Rule 3: Use Soft Delete for Important Entities

```sql
users, accounts, organizations → soft delete
logs, sessions, temp_data → hard delete OK
```

---

## Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| **CASCADE** | Automatic, clean | Can destroy unintended data |
| **Soft delete** | No data loss, reversible | Application changes, table growth |
| **NO ACTION** | Explicit control | Must cascade manually |
| **Archival** | Preserves data | Extra storage, complexity |

**Recommendation:** Soft delete for user data. Explicit cascade for owned content. Never CASCADE on shared content.

---

**Next Problem:** `advanced/postgres-107-generated-columns/`
