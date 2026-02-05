# Step 01: Understanding Hot Partitions

---

## Question 1: Why Is This Happening?

**Hash partitioning by channel_id causes all messages in #general to go to the same partition.**

```javascript
// Current partitioning
partition = hash(channel_id) % 32

// #general always hashes to partition 4
hash("general") % 32 = 4

// All 350 msg/sec go to partition 4
// Partition 4 consumer can only handle 100 msg/sec
// Result: Lag!
```

**The problem:** Hot key (#general) → Hot partition (p-4)

---

## Question 2: Fix Options

### Option 1: Increase Partitions

```javascript
// 32 → 128 partitions
partition = hash(channel_id) % 128

// #general now goes to different partition
// But ALL #general messages still go to same partition!
// Just spreads the hotness around
```

**Pros:** Simple, reduces hot key impact
**Cons:** Doesn't solve the root cause

### Option 2: Better Partition Key

```javascript
// Add timestamp to spread messages
partition = hash(channel_id + timestamp_minute) % 32

// Now #general messages spread across 32 partitions
// Each gets ~11 msg/sec instead of 350
```

**Pros:** Spreads load evenly
**Cons:** Messages from same channel not in order (need client-side ordering)

### Option 3: Key Salting

```javascript
// Add random suffix to partition key
partition = hash(channel_id + user_id) % 32

// Different users in #general go to different partitions
// Consumer processes need to reassemble
```

**Pros:** Spreads load, maintains ordering per user
**Cons:** More complex consumer logic

---

## Question 3: Prevention for All Channels

**Design for viral content:**

1. **Over-provision partitions:** Start with 64+ partitions
2. **Monitor lag per partition:** Alert before it gets bad
3. **Auto-scale consumers:** Add consumers when lag increases
4. **Design partitioning strategy:** Assume any channel can go viral

---

## Trade-offs

| Strategy | Order | Complexity | Best For |
|----------|-------|------------|----------|
| Increase partitions | Per channel | Low | Simple hot keys |
| Add timestamp | None | Medium | Firehose events |
| Salt with user_id | Per user | High | Chat, messaging |
| Random partitioning | None | Low | Analytics |

---

## Quick Check

Before moving on, make sure you understand:

1. What causes a hot partition? (When a single key gets all traffic, hashing to same partition)
2. Why does #general go to one partition? (All messages with same channel_id hash to same partition)
3. What's key salting? (Adding suffix like user_id to spread data across partitions)
4. What's the trade-off with timestamp-based partitioning? (Loses ordering within channel)
5. Why increase partitions instead of redesigning key? (Quick fix, but doesn't solve root cause)

---

**Want more implementation details? Read `step-02.md`**
