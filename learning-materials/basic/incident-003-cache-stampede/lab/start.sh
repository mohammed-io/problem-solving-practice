#!/bin/bash
# Cache Stampede Lab - One-Script Start

set -e

echo "💨 Cache Stampede Lab - Starting..."
echo ""

docker-compose up -d

echo "⏳ Waiting for Redis..."
for i in {1..20}; do
    if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        echo "  ✓ Redis ready!"
        break
    fi
    sleep 1
done

echo ""
echo "🧪 Running experiments..."
docker-compose run --rm client python scripts/client.py

trap "docker-compose down" EXIT
