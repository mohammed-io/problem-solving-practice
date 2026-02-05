#!/bin/bash
# Deadlock Lab - One-Script Start

set -e

echo "🔄 Deadlock Lab - Starting..."
echo ""

# Start services
docker-compose up -d

# Wait for PostgreSQL
echo "⏳ Waiting for PostgreSQL..."
for i in {1..30}; do
    if docker-compose exec -T postgres pg_isready -U admin > /dev/null 2>&1; then
        echo "  ✓ PostgreSQL ready!"
        break
    fi
    sleep 1
done

# Install dependencies
echo "📦 Installing Python dependencies..."
docker-compose exec -T client sh -c "
    pip install psycopg 2>/dev/null || pip3 install psycopg-binary 2>/dev/null || true
"

# Run experiments
echo ""
echo "🧪 Running experiments..."
docker-compose run --rm client python scripts/client.py

# Cleanup on exit
trap "docker-compose down -v" EXIT
