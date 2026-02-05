#!/bin/bash
# Quick start script for CAP Lab

set -e

echo "🎯 Starting CAP Theorem Lab..."
echo ""

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Start services
echo "🐳 Starting databases..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be ready..."

# Wait for etcd
echo "  Waiting for etcd..."
for i in {1..30}; do
    if docker-compose exec -T etcd1 etcdctl endpoint health > /dev/null 2>&1; then
        echo "  ✓ etcd ready!"
        break
    fi
    sleep 1
done

# Wait for MongoDB
echo "  Waiting for MongoDB..."
for i in {1..30}; do
    if docker-compose exec -T mongo1 mongosh --eval "db.adminCommand('ping')" > /dev/null 2>&1; then
        echo "  ✓ MongoDB ready!"
        break
    fi
    sleep 1
done

# Cassandra takes longer
echo "  Waiting for Cassandra (this takes ~60s)..."
for i in {1..60}; do
    if docker-compose exec -T cassandra1 nodetool status > /dev/null 2>&1; then
        echo "  ✓ Cassandra ready!"
        break
    fi
    sleep 1
done

echo ""
echo "✅ All systems ready!"
echo ""
echo "📋 Next steps:"
echo "  1. Check status: docker-compose ps"
echo "  2. Run experiments: docker-compose run --rm client python scripts/client.py"
echo "  3. Simulate partition: ./scripts/simulate_partition.sh test-cp"
echo "  4. Stop lab: docker-compose down -v"
echo ""
