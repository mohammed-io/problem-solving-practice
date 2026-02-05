# Step 1: Primary vs Replica Identification

---

## The Ambiguity Problem

**Confusing signals:**

```bash
# Check 1: pg_is_in_recovery()
SELECT pg_is_in_recovery();
-- Returns 't' on replica
-- Returns 'f' on primary
-- But: What if replica process crashed and it's confused?

# Check 2: pg_stat_replication
SELECT * FROM pg_stat_replication;
-- Shows replicas connected to THIS server
-- Empty on BOTH primary (if no replicas) AND replica (if it's a replica)
-- NOT RELIABLE to distinguish!

# Check 3: Process check
ps aux | grep walreceiver
-- Present on replica
-- Absent on primary (usually)
-- But: Crashed if replication broken!
```

---

## Unambiguous Identification

**Method 1: Use pg_controldata (authoritative)**

```bash
#!/bin/bash
# what_am_i.sh - Unambiguous server role identification

PGDATA="/var/lib/postgresql/14/main"

INFO=$(pg_controldata $PGDATA 2>/dev/null)

if echo "$INFO" | grep -q "in production = yes"; then
    echo "This server is a PRIMARY (read-write)"
    exit 0
elif echo "$INFO" | grep -q "in production = no"; then
    echo "This server is a REPLICA (read-only)"
    exit 0
else
    echo "ERROR: Could not determine role"
    exit 1
fi
```

**Method 2: Dedicated identification table**

```sql
-- Create on all servers during setup
CREATE TABLE cluster_identity (
    id INT PRIMARY KEY DEFAULT 1,
    server_name TEXT NOT NULL UNIQUE,
    server_role TEXT NOT NULL CHECK (server_role IN ('primary', 'replica')),
    is_primary BOOLEAN NOT NULL,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert correct value on each server
-- On primary:
INSERT INTO cluster_identity (id, server_name, server_role, is_primary)
VALUES (1, 'db1.cluster.gitlab.com', 'primary', true);

-- On replica:
INSERT INTO cluster_identity (id, server_name, server_role, is_primary)
VALUES (1, 'db2.cluster.gitlab.com', 'replica', false);

-- Now check with single query
SELECT * FROM cluster_identity;
```

**Method 3: Motd banner (visual identification)**

```bash
#!/bin/bash
# /etc/update-motd.d/99-postgresql-role

ROLE=$(pg_controldata /var/lib/postgresql/14/main 2>/dev/null | \
        grep "in production" | \
        awk '{print $NF}')

if [ "$ROLE" = "yes" ]; then
    cat << 'EOF'
╔═══════════════════════════════════════════════════════════╗
║  ⚠️  THIS SERVER IS A POSTGRESQL PRIMARY  ⚠️              ║
║  All writes go here. Replicas stream from this server.    ║
║  Be EXTRA CAREFUL with any commands!                      ║
╚═══════════════════════════════════════════════════════════╝
EOF
else
    cat << 'EOF'
╔═══════════════════════════════════════════════════════════╗
║  ℹ️  THIS SERVER IS A POSTGRESQL REPLICA  ℹ️              ║
║  Read-only. All changes come from primary via replication.║
║  DO NOT attempt to make this server writable!             ║
╚═══════════════════════════════════════════════════════════╝
EOF
fi
```

---

## The Replication Monitoring Gap

**What GitLab was missing:**

```go
package main

import (
    "database/sql"
    "fmt"
    "time"
    _ "github.com/lib/pq"
)

type ReplicationStatus struct {
    IsReplica             bool
    ReplicationLagBytes   *int64
    ReplicationLagSeconds *float64
    WalReceiverRunning    bool
    ConnectedReplicas     int
    SlotName              *string
}

func CheckReplicationStatus(db *sql.DB) (*ReplicationStatus, error) {
    status := &ReplicationStatus{}

    // Check if we're a replica
    var isReplica bool
    err := db.QueryRow("SELECT pg_is_in_recovery()").Scan(&isReplica)
    if err != nil {
        return nil, err
    }
    status.IsReplica = isReplica

    // Check replication lag
    if isReplica {
        var lagBytes int64
        var lagSeconds float64

        err := db.QueryRow(`
            SELECT pg_wal_lsn_diff(pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn()) as lag_bytes,
                   pg_wal_lsn_diff(pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn()) / 1024 / 1024 / 10
                   as lag_seconds_approx
        `).Scan(&lagBytes, &lagSeconds)

        if err == nil {
            status.ReplicationLagBytes = &lagBytes
            status.ReplicationLagSeconds = &lagSeconds
        }
    }

    // Check walreceiver process
    var walReceiverRunning bool
    err = db.QueryRow(`
        SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE application_name = 'walreceiver')
    `).Scan(&walReceiverRunning)
    if err == nil {
        status.WalReceiverRunning = walReceiverRunning
    }

    // Count connected replicas (if primary)
    if !isReplica {
        err = db.QueryRow("SELECT count(*) FROM pg_stat_replication").Scan(&status.ConnectedReplicas)
    }

    // Check replication slot status
    var slotName sql.NullString
    err = db.QueryRow(`
        SELECT slot_name FROM pg_replication_slots WHERE slot_type = 'physical' LIMIT 1
    `).Scan(&slotName)
    if err == nil && slotName.Valid {
        status.SlotName = &slotName.String
    }

    return status, nil
}

func MonitorReplication(db *sql.DB) {
    ticker := time.NewTicker(60 * time.Second)
    defer ticker.Stop()

    for range ticker.C {
        status, err := CheckReplicationStatus(db)
        if err != nil {
            fmt.Printf("Error checking replication: %v\n", err)
            continue
        }

        // Alert conditions
        if status.IsReplica {
            if status.ReplicationLagBytes != nil && *status.ReplicationLagBytes > 1_000_000_000 {
                Alert(fmt.Sprintf("CRITICAL: Replication lag: %.1f MB",
                    float64(*status.ReplicationLagBytes)/1024/1024))
            }

            if !status.WalReceiverRunning {
                Alert("CRITICAL: Walreceiver process not running!")
            }

            if status.ReplicationLagSeconds != nil && *status.ReplicationLagSeconds > 300 {
                Alert(fmt.Sprintf("WARNING: Replication lag: %.0f seconds",
                    *status.ReplicationLagSeconds))
            }
        } else {
            // We're primary
            if status.ConnectedReplicas == 0 {
                Alert("WARNING: No replicas connected to primary!")
            }
        }
    }
}

func Alert(message string) {
    fmt.Printf("[%s] %s\n", time.Now().Format("2006-01-02 15:04:05"), message)
    // send_to_pagerduty(message)
}
```

---

## Safe Recovery Procedures

**Before ANY destructive action:**

```bash
#!/bin/bash
# pre_destruction_check.sh - MANDATORY before rm, drop, truncate

set -e

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  DESTRUCTIVE OPERATION ABOUT TO OCCUR                    ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Confirm server role
echo "Step 1: Checking server role..."
ROLE=$(pg_controldata /var/lib/postgresql/14/main 2>/dev/null | \
        grep "in production" | awk '{print $NF}')

if [ "$ROLE" = "yes" ]; then
    echo "  ⚠️  You are on PRIMARY server"
    echo "  ⚠️  Data here is IRREPLACEABLE without backups!"
    read -p "  Type 'I-UNDERSTAND-THIS-IS-PRIMARY' to continue: " CONFIRM
    if [ "$CONFIRM" != "I-UNDERSTAND-THIS-IS-PRIMARY" ]; then
        echo "ABORTED"
        exit 1
    fi
else
    echo "  ℹ️  You are on REPLICA server"
    echo "  ℹ️  Data can be restored from primary"
fi

# Step 2: Check for connected replicas
echo ""
echo "Step 2: Checking for replicas..."
REPLICA_COUNT=$(psql -tAc "SELECT count(*) FROM pg_stat_replication")
if [ "$REPLICA_COUNT" -eq 0 ]; then
    echo "  ℹ️  No replicas connected"
else
    echo "  ⚠️  $REPLICA_COUNT replica(s) connected to this server!"
    read -p "  Type 'YES-REPLICAS-CONNECTED' to continue: " CONFIRM
    if [ "$CONFIRM" != "YES-REPLICAS-CONNECTED" ]; then
        echo "ABORTED"
        exit 1
    fi
fi

# Step 3: Create backup
echo ""
echo "Step 3: Creating snapshot before destruction..."
BACKUP_DIR="/var/backups/pre-destroy-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
echo "  Snapshot will be: $BACKUP_DIR"

# Step 4: Final confirmation
echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  FINAL CONFIRMATION REQUIRED                             ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "You are about to execute a DESTRUCTIVE operation."
echo "Server: $(hostname)"
echo "Role: $ROLE"
echo "Backup: $BACKUP_DIR"
echo ""
read -p "Type the exact command you intend to run: " COMMAND
echo ""
echo "You entered: $COMMAND"
read -p "Are you SURE? (yes/no): " FINAL

if [ "$FINAL" != "yes" ]; then
    echo "ABORTED"
    exit 1
fi

# Execute the command with logging
echo "Executing: $COMMAND" | tee -a /var/log/postgresql/destructive-ops.log
echo "Started: $(date)" | tee -a /var/log/postgresql/destructive-ops.log

eval "$COMMAND"

echo "Completed: $(date)" | tee -a /var/log/postgresql/destructive-ops.log
```

---

## Quick Check

Before moving on, make sure you understand:

1. Why is pg_is_in_recovery() not enough? (Returns false on both primary with no replicas AND broken replica)
2. What's pg_controldata? (Authoritative control data file showing if DB is in production mode)
3. Why was GitLab confused about primary vs replica? (Replication broken, replica confused, no clear identification)
4. What's a motd banner? (Message of the day - displays warning on SSH login for visual identification)
5. Why monitor replication lag? (Detect broken replication early before data diverges too much)

---

**Continue to `step-02.md`**
