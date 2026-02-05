#!/bin/bash
# Network Partition Simulator for CAP Lab

echo "╔════════════════════════════════════════════════════════════╗"
echo "║         CAP Theorem Lab - Partition Simulator               ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

case "$1" in
  status)
    echo "📊 Cluster Status:"
    echo ""
    echo "etcd nodes:"
    docker ps --filter "name=etcd" --format "  {{.Names}}: {{.Status}}"
    echo ""
    echo "Cassandra nodes:"
    docker ps --filter "name=cassandra" --format "  {{.Names}}: {{.Status}}"
    echo ""
    echo "MongoDB nodes:"
    docker ps --filter "name=mongo" --format "  {{.Names}}: {{.Status}}"
    ;;

  partition-etcd)
    echo "🔴 Partitioning etcd3..."
    docker pause etcd3
    echo "✓ etcd3 paused. quorum requires 2 of 3 nodes - etcd now degraded!"
    echo ""
    echo "To restore: $0 restore-etcd"
    ;;

  partition-cassandra)
    echo "🔴 Partitioning cassandra3..."
    docker pause cassandra3
    echo "✓ cassandra3 paused. Cassandra operates in AP mode - still available!"
    echo ""
    echo "To restore: $0 restore-cassandra"
    ;;

  partition-mongo)
    echo "🔴 Partitioning mongo3..."
    docker pause mongo3
    echo "✓ mongo3 paused. MongoDB behavior depends on write concern!"
    echo ""
    echo "To restore: $0 restore-mongo"
    ;;

  partition-all)
    echo "🔴 Partitioning one node from each cluster..."
    docker pause etcd3 cassandra3 mongo3
    echo "✓ All partitions active. Run experiments to see behavior!"
    echo ""
    echo "To restore: $0 restore-all"
    ;;

  restore-etcd)
    echo "🟢 Restoring etcd3..."
    docker unpause etcd3
    echo "✓ etcd3 restored. Full quorum available."
    ;;

  restore-cassandra)
    echo "🟢 Restoring cassandra3..."
    docker unpause cassandra3
    echo "✓ cassandra3 restored. Full replication available."
    ;;

  restore-mongo)
    echo "🟢 Restoring mongo3..."
    docker unpause mongo3
    echo "✓ mongo3 restored. Full replica set available."
    ;;

  restore-all)
    echo "🟢 Restoring all nodes..."
    docker unpause etcd3 cassandra3 mongo3
    echo "✓ All nodes restored. All clusters healthy."
    ;;

  test-cp)
    echo "🧪 Testing CP behavior (etcd during partition)..."
    docker pause etcd3
    sleep 2
    echo ""
    echo "Attempting to write to etcd..."
    docker-compose exec -T etcd1 etcdctl put test-key test-value || echo "❌ Write FAILED (expected for CP!)"
    docker unpause etcd3
    ;;

  test-ap)
    echo "🧪 Testing AP behavior (Cassandra during partition)..."
    docker pause cassandra3
    sleep 2
    echo ""
    echo "Attempting to write to Cassandra with CL=ONE..."
    docker-compose exec -T cassandra1 cqlsh -e "CONSISTENCY ONE; INSERT INTO cap_lab.test (key, value) VALUES ('test', 'value');" && echo "✓ Write SUCCEEDED (expected for AP!)"
    docker unpause cassandra3
    ;;

  *)
    echo "Usage: $0 {status|partition-etcd|partition-cassandra|partition-mongo|partition-all|restore-etcd|restore-cassandra|restore-mongo|restore-all|test-cp|test-ap}"
    echo ""
    echo "Examples:"
    echo "  $0 status              Show cluster status"
    echo "  $0 partition-etcd      Pause etcd3 (simulate partition)"
    echo "  $0 test-cp             Test CP behavior"
    echo "  $0 test-ap             Test AP behavior"
    echo "  $0 restore-all         Restore all nodes"
    exit 1
    ;;
esac
