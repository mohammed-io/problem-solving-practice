# Step 01: The Blocking Problem

---

## Why 2PC Blocks

After voting YES, participant enters PREPARED state:

```go
package twophase

import (
    "context"
    "fmt"
    "sync"
    "time"
)

type Vote int

const (
    VoteYes Vote = iota
    VoteNo
)

type TransactionState int

const (
    StateInitial TransactionState = iota
    StatePrepared
    StateCommitted
    StateAborted
)

type Participant struct {
    mu             sync.Mutex
    state          TransactionState
    lockedUntil    time.Time
    lockedResources []string
}

func (p *Participant) Prepare(ctx context.Context, tx *Transaction) (Vote, error) {
    p.mu.Lock()
    defer p.mu.Unlock()

    // Lock resources
    p.lockedResources = tx.Resources
    p.state = StatePrepared
    p.lockedUntil = time.Now().Add(30 * time.Second)

    return VoteYes, nil
}

func (p *Participant) Commit(ctx context.Context) error {
    p.mu.Lock()
    defer p.mu.Unlock()

    if p.state != StatePrepared {
        return fmt.Errorf("cannot commit non-prepared transaction (state: %d)", p.state)
    }

    // Apply changes
    if err := p.applyChanges(); err != nil {
        return err
    }

    // Release locks
    p.releaseLocks()
    p.state = StateCommitted
    return nil
}

func (p *Participant) Abort(ctx context.Context) error {
    p.mu.Lock()
    defer p.mu.Unlock()

    p.releaseLocks()
    p.state = StateAborted
    return nil
}

func (p *Participant) applyChanges() error {
    // Apply transaction changes
    return nil
}

func (p *Participant) releaseLocks() {
    p.lockedResources = nil
    p.lockedUntil = time.Time{}
}
```

**Problem:** If coordinator crashes after PREPARE, participant waits indefinitely with locked resources.

---

## Visual: Blocking Scenario

```
Time    Coordinator           Participant-1         Participant-2
        (orchestrates)         (holds Account-A)    (holds Account-B)

T0      PREPARE all            ────PREPARE───→       ────PREPARE───→
T1      (crashes!)             State=PREPARED        State=PREPARED
T2      XXXXX                   Waiting...             Waiting...
T3      XXXXX                   Locked for 30s         Locked for 30s
T4      XXXXX                   XXXXX                  XXXXX

Resources locked, no one can proceed
```

---

## Recovery: Presumed Abort

**Default strategy:** If coordinator unreachable, assume abort.

```go
func (p *Participant) WaitForCoordinator(ctx context.Context, txID string) error {
    ticker := time.NewTicker(1 * time.Second)
    defer ticker.Stop()

    timeout := time.After(30 * time.Second)

    for {
        select {
        case <-ctx.Done():
            return ctx.Err()
        case <-timeout:
            // Timeout: Presumed abort
            p.Abort(ctx)
            return fmt.Errorf("coordinator timeout, presumed abort")
        case <-ticker.C:
            // Check if coordinator recovered
            if p.checkCoordinatorStatus(txID) {
                return nil // Coordinator recovered
            }
        }
    }
}

func (p *Participant) checkCoordinatorStatus(txID string) bool {
    // In real implementation: check coordinator or log
    return false
}
```

**Issues with presumed abort:**
- What if coordinator DID commit but message lost?
- Inconsistency: Payment committed, Inventory aborted

---

## Recovery: Presumed Commit

**Opposite strategy:** Assume commit (for critical systems like payments).

```go
func (p *Participant) WaitForCoordinatorPresumeCommit(ctx context.Context, txID string) error {
    ticker := time.NewTicker(1 * time.Second)
    defer ticker.Stop()

    timeout := time.After(30 * time.Second)

    for {
        select {
        case <-ctx.Done():
            return ctx.Err()
        case <-timeout:
            // Timeout: Presumed commit (for critical systems)
            p.Commit(ctx)
            return fmt.Errorf("coordinator timeout, presumed commit")
        case <-ticker.C:
            if p.checkCoordinatorStatus(txID) {
                return nil
            }
        }
    }
}
```

**Issues with presumed commit:**
- What if coordinator actually aborted?
- Inconsistency: Inventory committed but Payment aborted!

---

## Neither is Perfect

```
┌─────────────────────────────────────────────────────────────┐
│  Recovery Strategy Tradeoffs:                              │
│                                                             │
│  Presumed Abort:                                           │
│    → Safer default (don't accidentally commit)            │
│    → But critical transactions may rollback incorrectly      │
│                                                             │
│  Presumed Commit:                                         │
│    → Better for payments (don't lose money)                │
│    → But may commit transactions that should have aborted    │
│                                                             │
│  Real Solution: Recovery Coordinator                        │
│    → Participants query each other                          │
│    → If any ABORTED, all ABORT                               │
│    → If all PREPARED, all COMMIT                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Check

Before moving on, make sure you understand:

1. Why does 2PC block? (Coordinator can crash after PREPARE, participants wait)
2. What is presumed abort? (Timeout = assume abort)
3. What is presumed commit? (Timeout = assume commit)
4. Why is neither perfect? (Message loss causes inconsistency)
5. What's the real solution? (Recovery coordinator or 3PC)

---

**Continue to `step-02.md`**
