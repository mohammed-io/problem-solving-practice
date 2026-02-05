#!/bin/bash
# Lease Lab - One-Script Start

set -e

echo "🔐 Lease Lab - Starting..."
echo ""

docker-compose up -d

echo "⏳ Waiting for etcd..."
for i in {1..30}; do
    if docker-compose exec -T etcd1 etcdctl endpoint health > /dev/null 2>&1; then
        echo "  ✓ etcd ready!"
        break
    fi
    sleep 1
done

echo ""
echo "🧪 Running experiments..."
docker-compose run --rm client python scripts/client.py

trap "docker-compose down" EXIT
