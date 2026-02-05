# Replica Lag Lab

Demonstrates streaming replication lag in PostgreSQL.

## Setup Required

Replica setup requires manual configuration. Run this after `docker-compose up -d`:

```bash
# On replica1
docker exec -it replica-lag-replica1 sh
rm -rf /var/lib/postgresql/data/*
pg_basebackup -h primary -D /var/lib/postgresql/data/pgdata -U replicator -P 5432
echo "standby_mode = on" >> /var/lib/postgresql/data/pgdata/postgresql.conf
echo "primary_conninfo = 'host=primary port=5432 user=replicator password=replicatepass'" >> /var/lib/postgresql/data/pgdata/postgresql.conf
pg_ctl -D /var/lib/postgresql/data/pgdata start

# Repeat for replica2
docker exec -it replica-lag-replica2 sh
rm -rf /var/lib/postgresql/data/*
pg_basebackup -h primary -D /var/lib/postgresql/data/pgdata -U replicator -P 5432
echo "standby_mode = on" >> /var/lib/postgresql/data/pgdata/postgresql.conf
echo "primary_conninfo = 'host=primary port=5432 user=replicator password=replicatepass'" >> /var/lib/postgresql/data/pgdata/postgresql.conf
pg_ctl -D /var/lib/postgresql/data/pgdata start
```

## Quick Start

```bash
docker-compose up -d
# Setup replicas (see above)
docker-compose run --rm client python scripts/client.py
```

## Cleanup

```bash
docker-compose down -v
```
