# Step 07: Fencing Tokens - Preventing Split-Brain

---

## The Problem

Network partitions can create **zombie leaders**.

```
┌─────────────────────────────────────────────────────────────┐
│  Timeline of Split-Brain:                                  │
│                                                             │
│  T0: Service A is leader                                   │
│      Service B is follower                                  │
│                                                             │
│  T1: Network partition isolates Service A                     │
│      ┌─────────────┐           ┌─────────────┐               │
│      │ Service A  │           │ Service B  │               │
│      │ (thinks     │           │             │               │
│      │ it's leader)│           │ Can't reach A│               │
│      └─────────────┘           │ Becomes     │               │
│                                │ leader!     │               │
│                                └─────────────┘               │
│                                                             │
│  T2: Both think they're leader!                            │
│      Service A writes to database                          │
│      Service B ALSO writes to database                       │
│                                                             │
│  💥 DATA CORRUPTION                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Solution: Fencing Tokens

Each leader gets a **fencing token** that must be included in all writes. The database validates the token.

```
┌─────────────────────────────────────────────────────────────┐
│  Fencing Token Flow:                                        │
│                                                             │
│  1. Service A becomes leader                                │
│     └─▶ Generates fencing-token: abc-123                     │
│     └─▶ Stores in etcd: /leader/fencing-token = abc-123    │
│                                                             │
│  2. Service A writes to database                              │
│     └─▶ Includes token: {data: {...}, token: "abc-123"}       │
│     └─▶ Database validates token against etcd                  │
│                                                             │
│  3. Network partition, Service B becomes leader              │
│     └─▶ Generates NEW fencing-token: def-456                   │
│     └─▶ Stores in etcd: /leader/fencing-token = def-456       │
│                                                             │
│  4. Service A (zombie) tries to write                         │
│     └─▶ Includes token: {data: {...}, token: "abc-123"}       │
│     └─▶ Database checks etcd: current token is def-456         │
│     └─▶ ❌ WRITE REJECTED!                                  │
│                                                             │
│  5. Service B writes with def-456                           │
│     └─▶ ✅ WRITE ACCEPTED                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation: Fencing Token Manager

```go
package coordination

import (
    "context"
    "time"

    clientv3 "go.etcd.io/etcd/client/v3"
    "github.com/google/uuid"
)

type FencingTokenManager struct {
    etcd *clientv3.Client
}

func NewFencingTokenManager(etcdEndpoints []string) (*FencingTokenManager, error) {
    cli, err := clientv3.New(clientv3.Config{
        Endpoints:   etcdEndpoints,
        DialTimeout: 5 * time.Second,
    })
    if err != nil {
        return nil, err
    }

    return &FencingTokenManager{etcd: cli}, nil
}

func (ftm *FencingTokenManager) GenerateToken(ctx context.Context, service string) (string, error) {
    // Generate fencing token
    token := uuid.New().String()

    // Store in etcd (overwrites any existing)
    key := "/leader/" + service + "/fencing-token"
    _, err := ftm.etcd.Put(ctx, key, token)
    if err != nil {
        return "", err
    }

    return token, nil
}

func (ftm *FencingTokenManager) ValidateToken(ctx context.Context, service, token string) (bool, error) {
    key := "/leader/" + service + "/fencing-token"
    resp, err := ftm.etcd.Get(ctx, key)
    if err != nil {
        return false, err
    }

    if len(resp.Kvs) == 0 {
        return false, nil // No token yet
    }

    currentToken := string(resp.Kvs[0].Value)
    return currentToken == token, nil
}

// Usage in leader election
type FencedLeader struct {
    tokenManager *FencingTokenManager
    fencingToken string
    serviceName   string
}

func (fl *FencedLeader) BecomeLeader(ctx context.Context) error {
    token, err := fl.tokenManager.GenerateToken(ctx, fl.serviceName)
    if err != nil {
        return err
    }

    fl.fencingToken = token
    return nil
}

func (fl *FencedLeader) IsWriteValid(ctx context.Context) (bool, error) {
    return fl.tokenManager.ValidateToken(ctx, fl.serviceName, fl.fencingToken)
}
```

---

## Database-Side Validation

The database must validate fencing tokens:

```sql
-- Table to track fencing tokens
CREATE TABLE fencing_tokens (
    service VARCHAR(50) NOT NULL,
    token UUID NOT NULL,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '1 minute',
    PRIMARY KEY (service, valid_until)
);

-- Check constraint (app-level)
-- Before write, check if token is valid
-- If token's valid_until < NOW(), reject write
```

Or implement as a database function:

```sql
CREATE OR REPLACE FUNCTION validate_fencing_token(
    p_service TEXT,
    p_token UUID
) RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM fencing_tokens
        WHERE service = p_service
        AND token = p_token
        AND valid_until > NOW()
    );
END;
$$ LANGUAGE plpgsql;

-- Usage in application
SELECT validate_fencing_token('order-service', 'abc-123'::uuid);
-- Returns: true (valid) or false (expired/invalid)
```

---

## Alternative: Generation Number

Instead of UUIDs, use **monotonically increasing numbers**:

```go
type GenerationNumber struct {
    etcd    *clientv3.Client
    keyPath string
}

func (gn *GenerationNumber) Increment(ctx context.Context) (int64, error) {
    // Compare-and-swap loop
    for {
        // Get current value
        resp, err := gn.etcd.Get(ctx, gn.keyPath)
        if err != nil {
            return 0, err
        }

        var currentGen int64
        if len(resp.Kvs) > 0 {
            currentGen, _ = strconv.ParseInt(string(resp.Kvs[0].Value), 10, 64)
        }

        // Increment
        newGen := currentGen + 1

        // Try to write (only succeeds if value hasn't changed)
        txn := gn.etcd.Txn(ctx)
        txn.Then(clientv3.OpPut(gn.keyPath, strconv.FormatInt(newGen, 10)))
        txn.Then(clientv3.OpGet(gn.keyPath)) // Verify
        resp, err := txn.Commit()
        if err != nil {
            continue // Retry
        }

        if resp.Succeeded {
            return newGen, nil
        }
    }
}

// Higher generation number = more recent leader
```

---

## Quick Check

Before moving on, make sure you understand:

1. What is the zombie leader problem? (Old leader thinks it's still leader after partition)
2. How do fencing tokens solve this? (Database validates current token)
3. What happens when a zombie leader tries to write? (Write is rejected)
4. What's an alternative to UUID tokens? (Generation numbers)

---

**Ready for service discovery and configuration? Read `step-08.md`**
