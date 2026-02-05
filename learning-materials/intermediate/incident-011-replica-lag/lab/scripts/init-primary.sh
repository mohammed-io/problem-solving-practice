#!/bin/bash
# Primary initialization script

# Setup replication configuration
cat >> /var/lib/postgresql/data/postgresql.conf <<EOF
wal_level = replica
max_wal_senders = 10
max_replication_slots = 10
hot_standby = on
EOF

# Create replication slot
echo "CREATE PUBLICATION publication_for_replication FOR ALL TABLES;" | psql -U admin -d appdb

# Create replication user
echo "CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD 'replicatepass';" | psql -U admin -d appdb
echo "ALTER ROLE replicator WITH REPLICATION PASSWORD 'replicatepass';" | psql -U admin -d appdb

# Grant permissions
echo "GRANT REPLICATION ON DATABASE appdb TO replicator;" | psql -U admin -d appdb

# Create test table
echo "CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    amount DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);" | psql -U admin -d appdb

echo "✓ Primary initialized"
