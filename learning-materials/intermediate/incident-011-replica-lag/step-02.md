# Step 02: Recovery and Prevention

---

## Recovery Steps

### 1. Check Replication Status

```sql
-- On primary
SELECT
    client_addr,
    state,
    sync_state,
    replay_lag,
    pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn)) as bytes_behind
FROM pg_stat_replication;
```

### 2. Catch Up Replica

**Option A: Stop writes temporarily**
```sql
-- On primary: Stop application writes
-- On replica: Let it catch up
-- On primary: Resume writes
```

**Option B: Rebuild replica (faster for large lag)**
```bash
# On replica: Stop PostgreSQL
sudo systemctl stop postgresql

# On replica: Remove old data
rm -rf /var/lib/postgresql/14/main

# On replica: Rebuild from primary
pg_basebackup -h primary.example.com -D /var/lib/postgresql/14/main -U replicator -P -v -R

# On replica: Start PostgreSQL
sudo systemctl start postgresql
```

### 3. Configure Streaming Replication

**On primary:**
```sql
-- Create replication slot (prevents WAL pruning)
SELECT * FROM pg_create_physical_replication_slot('replica1_slot');

-- Check replication
SELECT * FROM pg_stat_replication;
```

**On replica:**
```bash
# recovery.conf (PostgreSQL 11) or postgresql.conf + standby.signal (PostgreSQL 12+)
standby_mode = on
primary_conninfo = 'host=primary.example.com port=5432 user=replicator password=xxx'
primary_slot_name = 'replica1_slot'
restore_command = 'cp /var/lib/postgresql/archive/%f %p'
```

---

## Prevention

### 1. Monitor Lag Continuously

```python
import psycopg2
import time

def check_replica_lag():
    conn = psycopg2.connect("dbname=postgres host=replica")
    cur = conn.cursor()

    while True:
        cur.execute("SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))")
        lag_seconds = cur.fetchone()[0]

        if lag_seconds > 60:
            alert(f"Replica lag: {lag_seconds:.1f} seconds")

        time.sleep(10)
```

### 2. Circuit Breaker

```python
class ReplicaCircuitBreaker:
    def __init__(self, max_lag_seconds=60):
        self.max_lag = max_lag_seconds
        self.use_replica = True

    def check_lag(self):
        lag = self.get_replica_lag()
        if lag > self.max_lag:
            self.use_replica = False
            logger.warning(f"Replica lag too high ({lag}s), using primary")

    def query(self, sql, params=None):
        if self.use_replica:
            try:
                return self.replica.execute(sql, params)
            except Exception:
                self.use_replica = False

        return self.primary.execute(sql, params)
```

### 3. Load Balance Smartly

```
                    ┌─────────────┐
                    │   Primary   │
                    │  (Master)   │
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │                         │
         ┌────▼────┐              ┌────▼────┐
         │ Replica 1│              │ Replica 2│
         │ Lag: 5s  │              │ Lag: 3s  │
         └────┬────┘              └────┬────┘
              │                         │
              └────────┬────────────────┘
                       │
              ┌────────▼────────┐
              │  PgBouncer      │
              │  (Proxy)        │
              │  Routes based   │
              │  on lag check   │
              └─────────────────┘
```

---

## Summary

| Strategy | Implementation | Use Case |
|----------|----------------|----------|
| **Stop writes** | Temporary pause | Emergency, small lag |
| **Rebuild replica** | pg_basebackup | Large lag (> hours) |
| **Circuit breaker** | Route to primary on high lag | Always use |
| **Monitoring** | Alert on lag > 60s | Essential |
| **Replication slots** | Prevent WAL pruning | Production |

---

**Now read `solution.md` for complete reference.**
