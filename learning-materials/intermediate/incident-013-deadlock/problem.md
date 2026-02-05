---
name: incident-013-deadlock
description: Payment processing deadlock during high concurrency
difficulty: Intermediate
category: Database / Concurrency
level: Staff Engineer
---
# Incident 013: Database Deadlock

---

## Tools & Prerequisites

To debug database deadlock issues:

### Deadlock Detection Tools

| Tool | Purpose | Quick Usage |
|------|---------|-------------|
| **pg_stat_activity** | PostgreSQL blocking queries | `SELECT * FROM pg_stat_activity WHERE wait_event_type = 'Lock';` |
| **pg_locks** | Postgres lock details | `SELECT * FROM pg_locks WHERE NOT granted;` |
| **pg_blocking_pids** | Find blockers | `SELECT pg_blocking_pids(<pid>);` |
| **SHOW ENGINE INNODB STATUS** | MySQL deadlock info | `SHOW ENGINE INNODB STATUS\G` |
| **pt-deadlock-logger** | Monitor MySQL deadlocks | `pt-deadlock-logger --user=root` |
| **information_schema** | Lock wait details | `SELECT * FROM information_schema.innodb_locks;` |

### Key Commands

```bash
# PostgreSQL: Find blocked queries
psql -c "
SELECT
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query AS blocked_statement,
    blocking_activity.query AS blocking_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
"

# PostgreSQL: Check deadlocks count
psql -c "SELECT datname, deadlocks FROM pg_stat_database;"

# PostgreSQL: View lock details
psql -c "SELECT * FROM pg_locks WHERE pid = <pid>;"

# MySQL: Show InnoDB deadlock history
mysql -e "SHOW ENGINE INNODB STATUS\G" | grep -A 50 "LATEST DETECTED DEADLOCK"

# MySQL: Check lock waits
mysql -e "SELECT * FROM information_schema.innodb_lock_waits;"

# MySQL: Find blocking transactions
mysql -e "SELECT * FROM information_schema.innodb_trx;"

# Monitor long-held locks
watch -n 5 'psql -c "SELECT pid, now() - query_start AS duration, state, query FROM pg_stat_activity WHERE state IN (''idle in transaction'', ''active'') ORDER BY duration DESC;"'

# Enable PostgreSQL lock logging
psql -c "ALTER SYSTEM SET log_lock_waits = on;"
psql -c "ALTER SYSTEM SET log_duration = on;"

# Check transaction isolation level
psql -c "SHOW default_transaction_isolation;"

# Find long-running transactions
psql -c "SELECT pid, now() - xact_start AS duration, state, query FROM pg_stat_activity WHERE state NOT IN (''idle'') ORDER BY duration DESC;"

# Monitor deadlock rate over time
watch -n 10 'psql -c "SELECT deadlocks, xact_commit, xact_rollback FROM pg_stat_database WHERE datname = ''payments'';"'

# Check for lock contention
psql -c "SELECT relation::regclass, mode, count(*) FROM pg_locks GROUP BY relation, mode ORDER BY count DESC;"
```

### Key Concepts

**Deadlock**: Two or more transactions waiting for each other's locks in a circular wait pattern; database must kill one to break.

**Lock**: Database mechanism preventing concurrent access to same data; ensures data consistency.

**FOR UPDATE**: PostgreSQL clause locking selected rows until transaction ends; prevents other transactions from modifying.

**Lock Wait**: Transaction waiting for another transaction to release a lock.

**Blocking Transaction**: Transaction holding locks that other transactions are waiting for.

**Victim Selection**: Database choosing which transaction to abort to break deadlock; typically the most recent or youngest.

**Transaction Isolation Level**: Degree to which transactions are isolated from each other's changes (READ UNCOMMITTED, READ COMMITTED, REPEATABLE READ, SERIALIZABLE).

**Lock Timeout**: Maximum time to wait for lock before giving up (vs. deadlock detection).

**Lock Ordering**: Strategy of always acquiring locks in consistent order to prevent circular waits.

**Wait-for Graph**: Directed graph showing which transactions wait for which resources; cycle = deadlock.

**Two-Phase Locking**: Protocol where transactions acquire locks before releasing (growing phase then shrinking phase).

**Row-Level Lock**: Lock on individual row; allows other rows to be modified concurrently.

**Table-Level Lock**: Lock on entire table; prevents any concurrent modifications.

**Deadlock Detection**: Background process finding cycles in wait-for graph and killing victim transaction.

**Deadlock Prevention**: Design strategies (like lock ordering) to prevent deadlocks from occurring.

---

## The Situation

Your team runs a payment processing service. When a user makes a purchase:

1. **Lock the user's balance** (prevent double-spending)
2. **Lock the merchant's account** (ensure merchant receives payment)
3. **Transfer funds** (debit user, credit merchant)
4. **Release locks**

**Database:** PostgreSQL 14
**Transaction isolation:** READ COMMITTED (default)

---

## The Incident Report

```
Time: Tuesday, 10:30 AM UTC - Peak shopping hours

Issue: Payment transactions are failing with "deadlock detected"

Error: ERROR 40P01: deadlock detected
Detail: Process 123 waits for ShareLock on transaction 567;
       Process 456 waits for ShareLock on transaction 123.
       Process 123: UPDATE users SET balance = ... WHERE id = 10
       Process 456: UPDATE users SET balance = ... WHERE id = 20

Impact: ~15% of payment transactions failing
Severity: P0 (revenue impact)
```

---

## What is a Deadlock?

Imagine two people arrive at a narrow door at the same time.

**Person A** is on the left, steps right to let Person B pass.
**Person B** is on the right, steps left to let Person A pass.

Both are waiting for the other to move. Neither moves. They're **deadlocked**.

**In database terms:**
- Transaction A holds lock on row 1, waits for lock on row 2
- Transaction B holds lock on row 2, waits for lock on row 1
- Both wait forever → database kills one transaction

---

## What You See

### Application Logs

```
[ERROR] PaymentService: Transaction failed: deadlock detected
[INFO]  RetryService: Retrying transaction (attempt 2/3)
[ERROR] PaymentService: Transaction failed: deadlock detected
[INFO]  RetryService: Retrying transaction (attempt 3/3)
[ERROR] PaymentService: Transaction failed: deadlock detected
[ERROR] PaymentService: Payment failed after 3 retries
```

### Database Query (from pg_stat_database)

```sql
SELECT
  datname,
  deadlocks,
  xact_commit,
  xact_rollback
FROM pg_stat_database
WHERE datname = 'payments';
```

```
datname  | deadlocks | xact_commit | xact_rollback
---------|-----------|-------------|--------------
payments |    1,247  |     45,231  |      3,892
```

**1,247 deadlocks in the last hour!** (normally ~10/day)

### The Code

```go
func ProcessPayment(db *sql.DB, userID, merchantID int64, amount float64) error {
    tx, _ := db.Begin()
    defer tx.Rollback()

    // Step 1: Lock and debit user
    var userBalance float64
    tx.QueryRow("SELECT balance FROM users WHERE id = $1 FOR UPDATE", userID).
        Scan(&userBalance)

    if userBalance < amount {
        return errors.New("insufficient funds")
    }

    tx.Exec("UPDATE users SET balance = balance - $1 WHERE id = $2",
        amount, userID)

    // Step 2: Lock and credit merchant
    var merchantBalance float64
    tx.QueryRow("SELECT balance FROM users WHERE id = $1 FOR UPDATE", merchantID).
        Scan(&merchantBalance)

    tx.Exec("UPDATE users SET balance = balance + $1 WHERE id = $2",
        amount, merchantID)

    // Step 3: Record transaction
    tx.Exec(`INSERT INTO transactions (user_id, merchant_id, amount, created_at)
             VALUES ($1, $2, $3, NOW())`,
        userID, merchantID, amount)

    return tx.Commit()
}
```

---

## Traffic Pattern Analysis

Looking at failed transactions, you notice a pattern:

```
Time    | User A → Merchant X | User X → Merchant A
---------|---------------------|----------------------
10:30:00 |   ✓ Success        |   ✗ Deadlock
10:30:01 |   ✗ Deadlock       |   ✓ Success
10:30:02 |   ✓ Success        |   ✗ Deadlock
10:30:03 |   ✗ Deadlock       |   ✓ Success
```

**Pattern:** When user A pays merchant X, and simultaneously user X pays merchant A, a deadlock occurs!

---

## Jargon

| Term | Definition |
|------|------------|
| **Deadlock** | Two or more transactions waiting for each other's locks forever; database must kill one |
| **Lock** | Database mechanism to prevent concurrent modifications; ensures data consistency |
| **FOR UPDATE** | PostgreSQL clause that locks selected rows until transaction ends |
| **READ COMMITTED** | Isolation level where transactions see committed changes from other transactions |
| **Transaction** | Group of database operations treated as a single unit; all succeed or all fail |
| **Rollback** | Undoing a transaction; reverting all changes made within it |
| **Deadlock detector** | Background process that detects circular waits and kills one transaction |
| **Lock ordering** | Strategy to always acquire locks in a consistent order to prevent deadlocks |

---

## Questions

1. **Why is this happening only during peak hours?** (Think about concurrency)

2. **What's the specific deadlock pattern?** (Which locks are acquired in what order?)

3. **Why does "user A pays merchant X" and "user X pays merchant A" cause deadlock but not "user A pays merchant X" twice?**

4. **What are the fix options?** (Consider code changes, configuration, architecture)

5. **As a Staff Engineer, how do you design a payment system that's deadlock-free?**

---

**When you've thought about it, read `step-01.md`**
