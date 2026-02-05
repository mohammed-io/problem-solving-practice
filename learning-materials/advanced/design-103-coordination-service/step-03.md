# Step 03: Leader Election with Crash Recovery

---

## The Problem

Your leader service crashed. Now what?

```
┌─────────────────────────────────────────────────────────────┐
│  Before Crash:                                               │
│  ┌─────────┐                                                │
│  │Service A│ ← LEADER (doing primary work)                │
│  └─────────┘                                                │
│  ┌─────────┐                                                │
│  │Service B│ ← FOLLOWER (standing by)                     │
│  └─────────┘                                                │
│  ┌─────────┐                                                │
│  │Service C│ ← FOLLOWER (standing by)                     │
│  └─────────┘                                                │
└─────────────────────────────────────────────────────────────┘

💥 Service A crashes!

┌─────────────────────────────────────────────────────────────┐
│  After Crash:                                                │
│  ┌─────────┐                                                │
│  │Service A│ ← DEAD (was leader, not renewing)              │
│  └─────────┘                                                │
│  ┌─────────┐                                                │
│  │Service B│ ← Should become leader, but doesn't know yet!  │
│  └─────────┘                                                │
│  ┌─────────┐                                                │
│  │Service C│ ← Also wants to be leader!                    │
│  └─────────┘                                                │
│                                                             │
│  Result: No leader until manual intervention ❌             │
└─────────────────────────────────────────────────────────────┘
```

---

## Solution: TTL-Based Leadership

The leader **must continuously renew** its leadership. If it crashes, the TTL expires and others can take over.

```
┌─────────────────────────────────────────────────────────────┐
│  Leadership with TTL (Time To Live):                       │
│                                                             │
│  Service A becomes leader                                  │
│     └─▶ Sets key: /leadership/payment-service = "service-a"│
│         TTL: 10 seconds                                     │
│                                                             │
│  Every 5 seconds:                                          │
│     └─▶ Service A refreshes: extends TTL to 10s           │
│                                                             │
│  If Service A crashes:                                     │
│     └─▶ TTL not renewed                                    │
│     └─▶ After 10s, key expires                             │
│     └─▶ Service B and C see key is gone                    │
│     └─▶ They campaign for leadership                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation in Go

```go
package coordination

import (
    "context"
    "time"

    clientv3 "go.etcd.io/etcd/client/v3"
    "go.etcd.io/etcd/client/v3/concurrency"
)

type LeaderElection struct {
    client       *clientv3.Client
    electionPath string
    session      *concurrency.Session
    election     *concurrency.Election
    leader       bool
    onElected    func()
    onRemoved    func()
}

func NewLeaderElection(etcdEndpoints []string, electionPath string, onElected, onRemoved func()) (*LeaderElection, error) {
    cli, err := clientv3.New(clientv3.Config{
        Endpoints:   etcdEndpoints,
        DialTimeout: 5 * time.Second,
    })
    if err != nil {
        return nil, err
    }

    return &LeaderElection{
        client:       cli,
        electionPath: electionPath,
        onElected:    onElected,
        onRemoved:    onRemoved,
    }, nil
}

func (le *LeaderElection) Campaign(ctx context.Context) error {
    for {
        select {
        case <-ctx.Done():
            return ctx.Err()
        default:
        }

        // Create session with TTL
        session, err := concurrency.NewSession(ctx, le.client,
            concurrency.WithTTL(10)) // Leadership expires in 10s
        if err != nil {
            time.Sleep(time.Second)
            continue
        }
        le.session = session

        // Create election
        election := concurrency.NewElection(session, le.electionPath)
        le.election = election

        // Campaign for leadership
        if err := election.Campaign(ctx, "my-instance-id"); err != nil {
            time.Sleep(time.Second)
            continue
        }

        // I'm leader!
        le.leader = true
        if le.onElected != nil {
            le.onElected()
        }

        // Monitor leadership (this goroutine exits if we lose leadership)
        le.monitorLeadership(ctx)

        // If we get here, we lost leadership, retry campaign
    }
}

func (le *LeaderElection) monitorLeadership(ctx context.Context) {
    ch := le.election.Observe(ctx)

    for {
        select {
        case <-ctx.Done():
            return
        case resp := <-ch:
            // If we're no longer the leader
            if resp == nil || resp.Kvs == nil {
                le.leader = false
                if le.onRemoved != nil {
                    le.onRemoved()
                }
                return
            }
        }
    }
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. Why use TTL for leadership? (Auto-expire if leader crashes)
2. How often should TTL be renewed? (More frequently than TTL)
3. What happens when leader crashes? (TTL expires, others campaign)
4. What's the session used for? (Manages TTL auto-renewal)

---

**Ready for distributed locks? Read `step-04.md`**
