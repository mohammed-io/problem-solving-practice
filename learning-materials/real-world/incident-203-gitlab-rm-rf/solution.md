# Solution: Database Operations Safety

---

## Root Cause Analysis

**The human error chain:**
1. Replication monitoring was broken (lag detected but root cause unclear)
2. Engineer couldn't positively identify primary vs replica
3. Confusing diagnostic output (empty pg_stat_replication on both)
4. No automated failover (manual process prone to error)
5. Destructive command (`rm -rf`) without safety checks

**Three levels of failure:**
1. **Technical**: Ambiguous server role identification
2. **Process**: No mandatory safety checks before destructive ops
3. **Cultural**: Single engineer making catastrophic decision alone

---

## Complete Solution

### 1. Unambiguous Role Identification

**MOTD with server role:**

```bash
# /etc/profile.d/postgresql-role.sh
#!/bin/bash

# Get authoritative role from pg_controldata
PGDATA="/var/lib/postgresql/14/main"

if [ -f "$PGDATA/global/pg_control" ]; then
    ROLE=$(pg_controldata "$PGDATA" 2>/dev/null | grep "in production" | awk '{print $NF}')

    case "$ROLE" in
        yes)
            export PG_ROLE="PRIMARY"
            export PS1="\[\e[41m\]PRIMARY\[\e[0m\] \u@\h:\w\$ "
            ;;
        no)
            export PG_ROLE="REPLICA"
            export PS1="\[\e[44m\]REPLICA\[\e[0m\] \u@\h:\w\$ "
            ;;
        *)
            export PG_ROLE="UNKNOWN"
            export PS1="\[\e[43m\]UNKNOWN\[\e[0m\] \u@\h:\w\$ "
            ;;
    esac
fi

# Show banner on login
if [ -n "$SSH_CONNECTION" ]; then
    if [ "$PG_ROLE" = "PRIMARY" ]; then
        echo "═══════════════════════════════════════════════════════════"
        echo "  ⚠️  POSTGRESQL PRIMARY SERVER  ⚠️"
        echo "  This server handles ALL WRITE traffic"
        echo "  Data here is CRITICAL and IRREPLACEABLE"
        echo "═══════════════════════════════════════════════════════════"
    fi
fi
```

**API endpoint for role discovery:**

```python
from flask import Flask, jsonify
import subprocess

app = Flask(__name__)

@app.route('/api/role')
def get_role():
    """Return server role for monitoring systems."""
    try:
        result = subprocess.run(
            ['pg_controldata', '/var/lib/postgresql/14/main'],
            capture_output=True, text=True, timeout=5
        )

        for line in result.stdout.split('\n'):
            if 'in production' in line:
                is_primary = 'yes' in line
                return jsonify({
                    'role': 'primary' if is_primary else 'replica',
                    'hostname': subprocess.check_output(['hostname']).decode().strip(),
                    'timestamp': time.time()
                })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8008)
```

### 2. Automated Failover with Patroni

**Full Patroni cluster setup:**

```yaml
# /etc/patroni/patroni.yml
scope: gitlab-postgres
name: db1  # Unique per server

# REST API for health checks
restapi:
  listen: 0.0.0.0:8008
  connect_address: 10.0.1.10:8008

# Etcd for distributed consensus
bootstrap:
  dcs:
    ttl: 30
    loop_wait: 10
    retry_timeout: 10
    maximum_lag_on_failover: 1048576
    postgresql:
      use_pg_rewind: true
      remove_data_directory_on_rewind_failure: false

      # Parameters passed to postgres
      parameters:
        max_connections: 200
        shared_buffers: 32GB
        effective_cache_size: 96GB
        maintenance_work_mem: 2GB
        checkpoint_completion_target: 0.9
        wal_buffers: 16MB
        default_statistics_target: 100
        random_page_cost: 1.1
        effective_io_concurrency: 200
        work_mem: 4130kB
        min_wal_size: 2GB
        max_wal_size: 8GB

# PostgreSQL configuration
postgresql:
  listen: 0.0.0.0:5432
  connect_address: 10.0.1.10:5432
  data_dir: /var/lib/postgresql/14/main
  bin_dir: /usr/lib/postgresql/14/bin

  authentication:
    replication:
      username: replicator
      password: '__REDACTED__'
    superuser:
      username: postgres
      password: '__REDACTED__'

  # Replica creation methods
  create_replica_methods:
    - basebackup
    - pgbackrest

  basebackup:
    max-rate: '100M'
    checkpoint: 'fast'

  # Replication slots prevent WAL removal
  use_pg_rewind: true
  remove_data_directory_on_rewind_failure: false

# Tags for controlling behavior
tags:
  nofailover: false
  noloadbalance: false
  clonefrom: false
  nosync: false
```

**Monitoring Patroni cluster:**

```python
import requests
from typing import Dict, List

class PatroniCluster:
    def __init__(self, patroni_url: str):
        self.patroni_url = patroni_url

    def get_cluster_state(self) -> Dict:
        """Get current cluster state from Patroni REST API."""
        response = requests.get(f"{self.patroni_url}/config", timeout=5)
        response.raise_for_status()
        return response.json()

    def list_members(self) -> List[Dict]:
        """List all cluster members and their roles."""
        response = requests.get(f"{self.patroni_url}/members", timeout=5)
        response.raise_for_status()
        return response.json()['members']

    def get_primary(self) -> Dict:
        """Get current primary node info."""
        members = self.list_members()
        for member in members:
            if member['role'] == 'leader':
                return member
        raise ValueError("No primary found in cluster")

    def get_replicas(self) -> List[Dict]:
        """Get all replica nodes."""
        members = self.list_members()
        return [m for m in members if m['role'] == 'replica']

    def check_replication_lag(self) -> Dict[str, float]:
        """Check replication lag for all replicas."""
        lag = {}
        for replica in self.get_replicas():
            host = replica['host']
            # Query replica for lag
            conn = psycopg2.connect(f"host={host} user=postgres")
            cur = conn.cursor()
            cur.execute("""
                SELECT pg_wal_lsn_diff(
                    pg_last_wal_receive_lsn(),
                    pg_last_wal_replay_lsn()
                ) / 1024 / 1024 as lag_mb
            """)
            lag[host] = cur.fetchone()[0]
        return lag

# Usage in monitoring
cluster = PatroniCluster('http://patroni.gitlab.internal:8008')

# Alert if primary is unclear
try:
    primary = cluster.get_primary()
    print(f"Primary: {primary['host']}")
except ValueError:
    alert("No primary elected in Patroni cluster!")

# Alert on replication lag
lag = cluster.check_replication_lag()
for host, lag_mb in lag.items():
    if lag_mb > 100:  # 100 MB
        alert(f"Replication lag on {host}: {lag_mb:.1f} MB")
```

### 3. Safety Wrappers for Destructive Commands

**Alias rm to safe version:**

```bash
# /etc/profile.d/safe-rm.sh
#!/bin/bash

# Intercept dangerous commands
safe_rm() {
    # Check if targeting PostgreSQL data directory
    for arg in "$@"; do
        if [[ "$arg" == *"/postgresql/"* ]] || [[ "$arg" == *"/pgdata/"* ]]; then
            echo "╔═══════════════════════════════════════════════════════════╗"
            echo "║  ⚠️  DANGEROUS OPERATION DETECTED  ⚠️                    ║"
            echo "╚═══════════════════════════════════════════════════════════╝"
            echo ""
            echo "You are about to remove files in a PostgreSQL directory."
            echo ""
            echo "Server: $(hostname)"
            echo "Role: ${PG_ROLE:-unknown}"
            echo "Target: $@"
            echo ""
            echo "To proceed:"
            echo "1. Get approval from #database-ops channel"
            echo "2. Create snapshot: lvcreate -L 50G -s -n pg-snapshot /dev/vg0/pgdata"
            echo "3. Then run: \\rm $@ (backslash escapes alias)"
            echo ""
            return 1
        fi
    done

    # Safe to proceed
    /bin/rm "$@"
}

alias rm='safe_rm'
```

### 4. Immutable Infrastructure Pattern

**Treat databases as cattle, not pets:**

```terraform
# Terraform for PostgreSQL cluster
resource "aws_db_instance" "gitlab_primary" {
  identifier = "gitlab-primary-${var.environment}"

  # Automated backups
  backup_retention_period = 30
  backup_window = "03:00-04:00"
  maintenance_window = "Mon:04:00-Mon:05:00"

  # Multi-AZ for automatic failover
  multi_az = true
  db_subnet_group_name = aws_db_subnet_group.gitlab.name

  # Deletion protection
  deletion_protection = true
  skip_final_snapshot = false
  final_snapshot_identifier = "gitlab-final-${timestamp()}"

  # Performance
  instance_class = "db.r6g.2xlarge"
  allocated_storage = 1000
  storage_type = "gp3"
  iops = 20000

  tags = {
    Environment = var.environment
    Application = "gitlab"
    Backup = "required"
  }
}

# Read replicas for scale
resource "aws_db_instance" "gitlab_replica" {
  count = 2

  identifier = "gitlab-replica-${count.index}-${var.environment}"
  replicate_source_db = aws_db_instance.gitlab_primary.identifier

  instance_class = "db.r6g.xlarge"

  tags = {
    Type = "replica"
  }
}
```

---

## Trade-offs

| Approach | Safety | Complexity | Recovery Time |
|----------|--------|------------|---------------|
| **Manual operations** | Low (human error) | Low | Hours to days |
| **Patroni + Etcd** | High | Medium | Automatic (<1 min) |
| **Managed service (RDS)** | Very High | Low | Automatic |
| **Custom automation** | Variable | High | Depends on code |

**Recommendation:** Use managed service if possible. Otherwise, Patroni + Etcd.

---

## Real Incident: GitLab 2017

**What happened:**
- Engineer debugging replication lag
- Confused about primary vs replica status
- Ran `rm -rf /var/lib/postgresql/data` on what was thought to be broken replica
- Recovery took hours, caused major outage

**What changed:**
- Implemented Patroni for automated failover
- Added clear server identification (motd, prompts)
- Implemented mandatory peer review for destructive ops
- Moved to managed database service for some workloads
- Added comprehensive replication monitoring

**Postmortem quote:**
> "We had multiple single points of failure: human judgment, manual processes, and ambiguous tooling. We needed to eliminate all three."

---

## Prevention Checklist

**Before allowing database access:**
- [ ] Role identification (motd, prompt, API)
- [ ] Automated failover (Patroni/repmgr)
- [ ] Replication monitoring with alerts
- [ ] Mandatory snapshot before destructive ops
- [ ] Peer review requirement for production
- [ ] Recovery procedures tested quarterly
- [ ] Backup verification weekly
- [ ] Runbooks for all failure scenarios

---

**Next Problem:** `real-world/incident-204-facebook-bgp/`
