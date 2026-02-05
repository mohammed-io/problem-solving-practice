#!/bin/bash
# Write Skew Lab - One-Script Start

set -e

echo "🎫 Write Skew Lab - Starting..."
echo ""

docker-compose up -d

echo "⏳ Waiting for PostgreSQL..."
for i in {1..30}; do
    if docker-compose exec -T postgres pg_isready -U admin > /dev/null 2>&1; then
        echo "  ✓ PostgreSQL ready!"
        break
    fi
    sleep 1
done

echo "📦 Installing dependencies..."
docker-compose exec -T client sh -c "
    pip install psycopg-binary 2>/dev/null || true
"

echo ""
echo "🧪 Running experiments..."
docker-compose run --rm client python scripts/client.py

trap "docker-compose down -v" EXIT
