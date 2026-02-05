# Step 2: Safe Operations and Recovery

---

## Never Delete Data Directories

**The golden rule:**
```bash
# NEVER DO THIS:
sudo rm -rf /var/lib/postgresql/data

# INSTEAD: Use pg_rewind or take snapshot first
```

**Safe replication reset procedure:**

```bash
#!/bin/bash
# safe_replica_reset.sh - Rebuild replica WITHOUT data loss risk

PGDATA="/var/lib/postgresql/14/main"
PRIMARY_HOST="db1.cluster.gitlab.com"
BACKUP_BASE="/var/backups/postgresql"

echo "=== Safe Replica Rebuild ==="

# Step 1: Verify this is actually a replica
echo "Step 1: Verifying this is a replica..."
IS_REPLICA=$(psql -tAc "SELECT pg_is_in_recovery()")

if [ "$IS_REPLICA" != "t" ]; then
    echo "ERROR: This server is NOT a replica!"
    echo "ERROR: Aborting to prevent data loss."
    exit 1
fi
echo "  ✓ Confirmed: This is a replica"

# Step 2: Stop PostgreSQL
echo "Step 2: Stopping PostgreSQL..."
systemctl stop postgresql

# Step 3: RENAME old data directory (don't delete!)
echo "Step 3: Moving old data directory..."
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
OLD_DATA="${PGDATA}.old.${TIMESTAMP}"
mv "$PGDATA" "$OLD_DATA"
echo "  ✓ Old data preserved at: $OLD_DATA"

# Step 4: Use pg_basebackup to get fresh copy from primary
echo "Step 4: Running pg_basebackup from primary..."
mkdir -p "$PGDATA"
chmod 700 "$PGDATA"

pg_basebackup \
    -h "$PRIMARY_HOST" \
    -D "$PGDATA" \
    -U replication_user \
    -P \
    -R \
    -X stream \
    -C -S replica_slot_$(hostname) \
    --wal-method=stream

echo "  ✓ Fresh replica data copied"

# Step 5: Start PostgreSQL
echo "Step 5: Starting PostgreSQL..."
systemctl start postgresql

# Step 6: Verify replication
echo "Step 6: Verifying replication..."
sleep 5
REPLICATION_STATUS=$(psql -tAc "SELECT pg_is_in_recovery()")

if [ "$REPLICATION_STATUS" = "t" ]; then
    echo "  ✓ Replication working"
else
    echo "  ✗ Replication not working!"
    echo "  Restoring old data..."
    systemctl stop postgresql
    rm -rf "$PGDATA"
    mv "$OLD_DATA" "$PGDATA"
    systemctl start postgresql
    exit 1
fi

# Step 7: Cleanup (after 7 days)
echo "Step 7: Scheduling old data cleanup..."
echo "find /var/lib/postgresql -name '*.old.*' -mtime +7 -exec rm -rf {} +;" | \
    at now + 7 days

echo "=== Replica rebuild complete ==="
```

---

## Automated Failover with Patroni

**Prevent split brain with automated failover:**

```yaml
# patroni.yml - Distributed PostgreSQL high availability
scope: gitlab-postgres
name: db1.cluster.gitlab.com

restapi:
  listen: 0.0.0.0:8008
  connect_address: db1.cluster.gitlab.com:8008

# Use etcd for distributed consensus
bootstrap:
  dcs:
    ttl: 30
    loop_wait: 10
    retry_timeout: 10
    maximum_lag_on_failover: 1048576

postgresql:
  listen: 0.0.0.0:5432
  connect_address: db1.cluster.gitlab.com:5432
  data_dir: /var/lib/postgresql/14/main
  bin_dir: /usr/lib/postgresql/14/bin

  authentication:
    replication:
      username: replicator
      password: '__REPL_PASSWORD__'

  # Replication configuration
  create_replica_method:
    - basebackup
    - pgbackrest

  basebackup:
    max-rate: '100M'
    checkpoint: 'fast'

tags:
  nofailover: false
  noloadbalance: false
  clonefrom: false
  nosync: false
```

**How Patroni prevents the GitLab issue:**

1. **Distributed consensus:** All nodes agree on who is primary
2. **Automatic health checks:** Unhealthy primary is demoted
3. **Safe failover:** Replica promoted only with quorum agreement
4. **Configuration stored in DCS:** No manual confusion about roles

```bash
# Check cluster status
$ patronictl -c /etc/patroni/patronictl.yml list
+ Cluster: gitlab-postgres ----+----+-----------+
| Member       | Host           | Role    | State   |
+--------------+----------------+---------+---------+
| db1          | 10.0.1.10      | Leader  | running |
| db2          | 10.0.1.11      | Replica | running |
| db3          | 10.0.1.12      | Replica | running |
+--------------+----------------+---------+---------+

# No ambiguity about who is primary!

# Failover (manual)
$ patronictl switchover
Master [db1]: db1
Candidate ['db2', 'db3'] []: db2
When should the switchover take place (e.g. 2023-01-01T17:23) [now]:
Are you sure you want to switchover cluster 'gitlab-postgres', demoting current master 'db1'? [yes/n]: yes
2023-01-01 17:23:45.33211 Successfully switchover to 'db2'
```

---

## The GitLab Recovery Process

**What actually happened during recovery:**

```
1. Realized db2 had deleted (stale) data
2. Checked db1 - it had 24 hours of data but replication was broken
3. Restored from LVM snapshot (6 hours old)
4. Replay WAL logs to get to current state
5. Verification process
6. Back online
```

**Better approach (what should have happened):**

```bash
#!/bin/bash
# emergency_failover.sh - When primary is suspect

# 1: Immediately take LVM snapshot of current primary
# 2: Spin up replica from snapshot
# 3: Test replica for data integrity
# 4: ONLY THEN demote old primary
# 5: Promote new primary
# 6: Verify all systems

# This way, you can always roll back
```

---

## Operational Safety Checklist

**Before any database operation:**

```go
package main

import (
    "bufio"
    "fmt"
    "os"
    "strings"
)

type DBChecklist struct {
    checks []ChecklistItem
}

type ChecklistItem struct {
    Description string
    Done        bool
}

func (c *DBChecklist) Run() error {
    fmt.Println("╔═══════════════════════════════════════════════════════════╗")
    fmt.Println("║  Database Operation Safety Checklist                    ║")
    fmt.Println("╚═══════════════════════════════════════════════════════════╝")
    fmt.Println()

    checks := []string{
        "Verified which server I'm on",
        "Confirmed role (primary/replica) using pg_controldata",
        "Checked for connected replicas",
        "Verified backup exists and is recent",
        "Created snapshot before destructive operation",
        "Have rollback plan documented",
        "Confirmed with teammate",
        "Maintenance window announced",
    }

    reader := bufio.NewReader(os.Stdin)
    allDone := true

    for i, check := range checks {
        fmt.Printf("[%d] %s\n", i+1, check)
        fmt.Print("    Done? [y/n] ")
        input, _ := reader.ReadString('\n')
        input = strings.TrimSpace(input)

        if input != "y" && input != "Y" {
            allDone = false
        }
    }

    if !allDone {
        fmt.Println()
        fmt.Println("⚠️  Not all checklist items complete.")
        fmt.Print("Continue anyway? (type OVERRIDE): ")
        input, _ := reader.ReadString('\n')
        input = strings.TrimSpace(input)

        if input != "OVERRIDE" {
            return fmt.Errorf("operation aborted by user")
        }
    }

    return nil
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. Why use pg_basebackup instead of rm -rf? (Preserves old data as backup, can rollback if something goes wrong)
2. What's Patroni? (Distributed PostgreSQL HA system using consensus for automatic failover)
3. How does Patroni prevent GitLab-style incidents? (Distributed consensus prevents split-brain, clear leader election)
4. What's the pre-destruction checklist pattern? (Verify server role, check replicas, confirm backups, get approval)
5. Why take LVM snapshot before failover? (Preserves current state for rollback if failover goes wrong)

---

**Continue to `solution.md`**
