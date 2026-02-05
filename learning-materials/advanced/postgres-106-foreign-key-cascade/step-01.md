# Step 1: Visualizing Cascade Network

---

## The Dependency Graph

```
     ┌─────────────┐
     │    users    │
     └──────┬──────┘
            │ user_id
            ▼
     ┌─────────────┐
     │    posts    │
     └──────┬──────┘
            │ post_id
            ▼
     ┌─────────────┐
     │  comments   │
     └──────┬──────┘
            │ user_id (coming back!)
            └─────────────┘

Delete user → Delete posts → Delete comments → (but comments also have user_id!)
```

**If both FKs have ON DELETE CASCADE:**
- Delete user 123
- Posts by user 123 deleted
- Comments on those posts deleted (even by other users!)
- Comments by user 123 also deleted (on other posts)

---

## The Danger

```
User 123 posts on post 999
User 456 comments on post 999

Delete user 123:
→ Post 999 deleted (user_id FK CASCADE)
→ Comment by 456 on post 999 deleted (post_id FK CASCADE)

User 456 lost their comment, but they didn't do anything wrong!
```

**CASCADE can destroy other users' data!**

---

## Quick Check

Before moving on, make sure you understand:

1. What is the danger of CASCADE? (Can delete other users' data unintentionally)
2. Why does CASCADE affect other users? (Deletes cascade through all FK relationships)
3. What happens in a circular FK relationship? (Both FK cascades trigger, data loss)
4. How can user 456 lose data when user 123 is deleted? (CASCADE on post_id deletes 456's comments)
5. Why is CASCADE dangerous in production? (Hard to predict impact, can't undo)

---

**Continue to `step-02.md`**
