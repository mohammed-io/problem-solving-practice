#!/bin/bash
# Replica Lag Lab - Start

set -e

echo "📊 Replica Lag Lab - Starting..."
echo ""

docker-compose up -d

echo "⏳ Waiting for primary..."
for i in {1..30}; do
    if docker-compose exec -T primary pg_isready -U admin > /dev/null 2>&1; then
        echo "  ✓ Primary ready!"
        break
    fi
    sleep 1
done

echo ""
echo "⚠️  Manual setup required for replicas. See README.md"
echo "    Replicas require pg_basebackup from primary."
echo ""
echo "📋 Running limited experiments..."
docker-compose run --rm client python scripts/client.py
