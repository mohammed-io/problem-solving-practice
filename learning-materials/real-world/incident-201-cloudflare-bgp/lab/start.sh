#!/bin/bash
# BGP Lab - One-Script Start

set -e

echo "🌐 BGP Route Leak Lab - Starting..."
echo ""

docker-compose up -d

echo "⏳ Waiting for BGP daemons to start..."
sleep 10

echo "⏳ Waiting for BGP sessions to establish..."
for i in {1..30}; do
    if docker-compose exec -T backbone vtysh -c "show ip bgp summary" | grep -q "Establ"; then
        echo "  ✓ BGP sessions established!"
        break
    fi
    sleep 1
done

echo ""
echo "🧪 Running experiments..."
docker-compose run --rm client python scripts/client.py

trap "docker-compose down" EXIT
