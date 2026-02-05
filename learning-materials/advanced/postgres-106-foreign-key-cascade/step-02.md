# Step 2: Safer Alternatives

---

## Solution 1: Soft Delete

```sql
ALTER TABLE users ADD COLUMN deleted_at TIMESTAMPTZ;

-- Instead of DELETE
UPDATE users SET deleted_at = NOW() WHERE id = 123;

-- Application filters on deleted_at
SELECT * FROM users WHERE deleted_at IS NULL;
```

**Cascade never happens!** Data preserved, can be undone.

---

## Solution 2: Use RESTRICT or NO ACTION

```sql
-- Change FK to prevent accidental cascades
ALTER TABLE posts
DROP CONSTRAINT posts_user_id_fkey,
ADD CONSTRAINT posts_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE RESTRICT;  -- Prevent deletion if referenced

-- Now deletion must be explicit
BEGIN;
-- First delete child rows
DELETE FROM comments WHERE user_id = 123;
DELETE FROM posts WHERE user_id = 123;
-- Then delete user
DELETE FROM users WHERE id = 123;
COMMIT;
```

**Benefits:**
- Explicit about what gets deleted
- Can audit cascade path
- Can preserve important data

---

## Solution 3: Application-Level Cascade

```sql
-- Remove CASCADE from FK
ALTER TABLE comments
DROP CONSTRAINT comments_user_id_fkey,
ADD CONSTRAINT comments_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE NO ACTION;
```

```go
func deleteUserSafely(db *sql.DB, userID int64) error {
    tx, _ := db.Begin()
    defer tx.Rollback()

    // Show what will be deleted
    impact := analyzeCascadeImpact(tx, userID)
    if impact.CommentsByOthers > 0 {
        return errors.New("cannot delete: other users' comments affected")
    }

    // Explicit cascade
    deleteCommentsByUser(tx, userID)
    deletePostsByUser(tx, userID)
    deleteUser(tx, userID)

    return tx.Commit()
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What is soft delete? (Mark as deleted with timestamp instead of actual DELETE)
2. What's the benefit of soft delete? (No CASCADE, data preserved, reversible)
3. What does ON DELETE RESTRICT do? (Prevents deletion if referenced rows exist)
4. Why use application-level cascade? (Explicit control, can audit, preserve important data)
5. What's the tradeoff of soft delete? (Must filter queries, storage overhead)

---

**Continue to `solution.md`**
