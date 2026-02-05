#!/usr/bin/env python3
"""
CAP Theorem Lab - Experiment Client

This script demonstrates the CAP theorem tradeoffs using:
- etcd: CP (Consistency over Availability)
- Cassandra: AP (Availability over Consistency, tunable)
- MongoDB: Configurable (write concern determines behavior)
"""

import asyncio
import time
import json
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Literal

# pip install etcd3 cassandra-driver pymongo
import etcd3
from cassandra.cluster import Cluster
from cassandra.query import ConsistencyLevel
from pymongo import MongoClient
from pymongo import WriteConcern


@dataclass
class ExperimentResult:
    system: str
    operation: str
    success: bool
    latency_ms: float
    error: Optional[str] = None
    value: Optional[str] = None


class CAPLabClient:
    """Client for testing CAP properties across different systems"""

    def __init__(self):
        # etcd endpoints (CP)
        self.etcd_endpoints = ["etcd1:2379", "etcd2:2379", "etcd3:2379"]

        # Cassandra endpoints (AP)
        self.cassandra_endpoints = ["cassandra1", "cassandra2", "cassandra3"]

        # MongoDB endpoints (Configurable)
        self.mongo_endpoints = ["mongo1:27017", "mongo2:27017", "mongo3:27017"]

    # ============================================
    # etcd (CP System)
    # ============================================
    async def test_etcd_write(self, key: str, value: str) -> ExperimentResult:
        """Write to etcd - CP system, expects strong consistency"""
        start = time.time()
        try:
            etcd = etcd3.client(hosts=self.etcd_endpoints, timeout=5)
            etcd.put(key, value)
            latency = (time.time() - start) * 1000
            return ExperimentResult("etcd", "write", True, latency, value=value)
        except Exception as e:
            latency = (time.time() - start) * 1000
            return ExperimentResult("etcd", "write", False, latency, str(e))

    async def test_etcd_read(self, key: str) -> ExperimentResult:
        """Read from etcd - CP system, always consistent"""
        start = time.time()
        try:
            etcd = etcd3.client(hosts=self.etcd_endpoints, timeout=5)
            value, _ = etcd.get(key)
            latency = (time.time() - start) * 1000
            return ExperimentResult("etcd", "read", True, latency, value=value.decode() if value else None)
        except Exception as e:
            latency = (time.time() - start) * 1000
            return ExperimentResult("etcd", "read", False, latency, str(e))

    # ============================================
    # Cassandra (AP System)
    # ============================================
    async def test_cassandra_write(self, table: str, key: str, value: str,
                                    cl: ConsistencyLevel = ConsistencyLevel.QUORUM) -> ExperimentResult:
        """Write to Cassandra - AP system, tunable consistency"""
        start = time.time()
        try:
            cluster = Cluster(self.cassandra_endpoints)
            session = cluster.connect()
            session.execute(f"""
                CREATE KEYSPACE IF NOT EXISTS cap_lab
                WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': 3}}
            """)
            session.set_keyspace('cap_lab')
            session.execute(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    key text PRIMARY KEY,
                    value text,
                    updated_at timestamp
                )
            """)

            query = f"INSERT INTO {table} (key, value, updated_at) VALUES (%s, %s, toTimestamp(now()))"
            session.execute(query, (key, value), timeout=5)
            latency = (time.time() - start) * 1000
            cluster.shutdown()
            return ExperimentResult(f"cassandra-{cl.name}", "write", True, latency)
        except Exception as e:
            latency = (time.time() - start) * 1000
            return ExperimentResult(f"cassandra-{cl.name}", "write", False, latency, str(e))

    async def test_cassandra_read(self, table: str, key: str,
                                   cl: ConsistencyLevel = ConsistencyLevel.QUORUM) -> ExperimentResult:
        """Read from Cassandra - AP system, tunable consistency"""
        start = time.time()
        try:
            cluster = Cluster(self.cassandra_endpoints)
            session = cluster.connect()
            session.set_keyspace('cap_lab')

            query = f"SELECT value FROM {table} WHERE key = %s"
            rows = session.execute(query, (key,), timeout=5)
            result = rows.one()
            latency = (time.time() - start) * 1000
            cluster.shutdown()
            return ExperimentResult(f"cassandra-{cl.name}", "read", True, latency,
                                    value=result.value if result else None)
        except Exception as e:
            latency = (time.time() - start) * 1000
            return ExperimentResult(f"cassandra-{cl.name}", "read", False, latency, str(e))

    # ============================================
    # MongoDB (Configurable)
    # ============================================
    async def test_mongo_write(self, database: str, collection: str, key: str, value: str,
                                write_concern: Literal['w1', 'majority', 'w3'] = 'majority') -> ExperimentResult:
        """Write to MongoDB - configurable via write concern"""
        start = time.time()
        try:
            client = MongoClient(self.mongo_endpoints,
                                replicaSet='rs0',
                                serverSelectionTimeoutMS=5000)

            db = client[database]
            coll = db[collection]

            # Set write concern
            wc = {'w1': WriteConcern.W1,
                  'majority': WriteConcern.MAJORITY,
                  'w3': WriteConcern.W_THREE}[write_concern]

            coll = coll.with_options(write_concern=wc)
            coll.update_one(
                {'_id': key},
                {'$set': {'value': value, 'updated_at': datetime.utcnow()}},
                upsert=True
            )
            latency = (time.time() - start) * 1000
            client.close()
            return ExperimentResult(f"mongo-{write_concern}", "write", True, latency)
        except Exception as e:
            latency = (time.time() - start) * 1000
            return ExperimentResult(f"mongo-{write_concern}", "write", False, latency, str(e))

    async def test_mongo_read(self, database: str, collection: str, key: str,
                              read_preference: Literal['primary', 'secondary'] = 'primary') -> ExperimentResult:
        """Read from MongoDB - configurable via read preference"""
        start = time.time()
        try:
            client = MongoClient(self.mongo_endpoints,
                                replicaSet='rs0',
                                serverSelectionTimeoutMS=5000)

            db = client[database]
            coll = db[collection]

            doc = coll.find_one({'_id': key})
            latency = (time.time() - start) * 1000
            client.close()
            return ExperimentResult(f"mongo-{read_preference}", "read", True, latency,
                                    value=doc['value'] if doc else None)
        except Exception as e:
            latency = (time.time() - start) * 1000
            return ExperimentResult(f"mongo-{read_preference}", "read", False, latency, str(e))


# ============================================
# EXPERIMENTS
# ============================================

async def experiment_1_normal_operations(client: CAPLabClient):
    """Experiment 1: All systems healthy - measure baseline latency"""
    print("\n" + "="*60)
    print("EXPERIMENT 1: Normal Operations (All Healthy)")
    print("="*60)

    key = "test-key-1"
    value = "test-value-1"

    results = []

    # Test etcd
    print("\n[etcd] Testing CP system...")
    result = await client.test_etcd_write(key, value)
    results.append(result)
    print(f"  Write: {result.success} | {result.latency_ms:.1f}ms")
    result = await client.test_etcd_read(key)
    results.append(result)
    print(f"  Read:  {result.success} | {result.latency_ms:.1f}ms | value='{result.value}'")

    # Test Cassandra with QUORUM
    print("\n[cassandra] Testing AP system (QUORUM)...")
    result = await client.test_cassandra_write("test_table", key, value, ConsistencyLevel.QUORUM)
    results.append(result)
    print(f"  Write: {result.success} | {result.latency_ms:.1f}ms")
    result = await client.test_cassandra_read("test_table", key, ConsistencyLevel.QUORUM)
    results.append(result)
    print(f"  Read:  {result.success} | {result.latency_ms:.1f}ms")

    # Test MongoDB with majority
    print("\n[mongodb] Testing configurable system (majority)...")
    result = await client.test_mongo_write("cap_lab", "test_col", key, value, "majority")
    results.append(result)
    print(f"  Write: {result.success} | {result.latency_ms:.1f}ms")
    result = await client.test_mongo_read("cap_lab", "test_col", key, "primary")
    results.append(result)
    print(f"  Read:  {result.success} | {result.latency_ms:.1f}ms")

    save_results("experiment_1_normal.json", results)
    return results


async def experiment_2_partition_simulation(client: CAPLabClient):
    """Experiment 2: Simulate network partition by stopping one node"""
    print("\n" + "="*60)
    print("EXPERIMENT 2: Network Partition (Stop etcd3)")
    print("="*60)
    print("\nACTION REQUIRED: Run this in another terminal:")
    print("  docker pause etcd3")
    print("\nPress Enter when ready...")
    input()

    key = "partition-test"
    value = "should-fail-on-cp"

    results = []

    # Test etcd (CP) - should fail or timeout
    print("\n[etcd] Testing CP system during partition...")
    result = await client.test_etcd_write(key, value)
    results.append(result)
    if result.success:
        print(f"  Write: {result.success} | {result.latency_ms:.1f}ms | ⚠️  Quorum still available!")
    else:
        print(f"  Write: {result.success} | {result.latency_ms:.1f}ms | ✓ Correctly rejected (CP)")

    # Test Cassandra with ONE (AP) - should succeed
    print("\n[cassandra] Testing AP system (ONE) during partition...")
    result = await client.test_cassandra_write("test_table", key, value, ConsistencyLevel.ONE)
    results.append(result)
    print(f"  Write: {result.success} | {result.latency_ms:.1f}ms | {'✓ Available (AP)' if result.success else '✗ Failed'}")

    # Test MongoDB with w=1 (AP-like) - should succeed
    print("\n[mongodb] Testing with w=1 during partition...")
    result = await client.test_mongo_write("cap_lab", "test_col", key, value, "w1")
    results.append(result)
    print(f"  Write: {result.success} | {result.latency_ms:.1f}ms | {'✓ Available' if result.success else '✗ Failed'}")

    # Test MongoDB with majority (CP-like) - might fail
    print("\n[mongodb] Testing with majority during partition...")
    result = await client.test_mongo_write("cap_lab", "test_col", "partition-key", "value", "majority")
    results.append(result)
    if result.success:
        print(f"  Write: {result.success} | {result.latency_ms:.1f}ms | ⚠️  Quorum still available")
    else:
        print(f"  Write: {result.success} | {result.latency_ms:.1f}ms | ✓ Correctly rejected")

    print("\nACTION: Restore etcd3 - docker unpause etcd3")
    save_results("experiment_2_partition.json", results)
    return results


async def experiment_3_consistency_levels(client: CAPLabClient):
    """Experiment 3: Test different consistency levels on Cassandra"""
    print("\n" + "="*60)
    print("EXPERIMENT 3: Cassandra Consistency Levels")
    print("="*60)

    key = "consistency-test"
    value = "consistency-value"

    results = []

    for cl in [ConsistencyLevel.ONE, ConsistencyLevel.QUORUM, ConsistencyLevel.ALL]:
        print(f"\n[cassandra] Testing with CL={cl.name}...")
        result = await client.test_cassandra_write("test_table", key, value, cl)
        results.append(result)
        print(f"  Write: {result.success} | {result.latency_ms:.1f}ms | {'✓' if result.success else '✗'}")

    save_results("experiment_3_consistency.json", results)
    return results


def save_results(filename: str, results: list[ExperimentResult]):
    """Save experiment results to JSON file"""
    output = []
    for r in results:
        output.append({
            'system': r.system,
            'operation': r.operation,
            'success': r.success,
            'latency_ms': round(r.latency_ms, 2),
            'error': r.error,
            'value': r.value,
            'timestamp': datetime.utcnow().isoformat()
        })

    with open(f'/workspace/results/{filename}', 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n💾 Results saved to results/{filename}")


def print_summary():
    """Print experiment summary"""
    print("\n" + "="*60)
    print("CAP THEOREM LAB - SUMMARY")
    print("="*60)
    print("""
┌─────────────────────────────────────────────────────────────────┐
│                     CAP Theorem Triangle                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                   Consistency                                   │
│                      ✓✓✓                                       │
│                     ✓   ✓                                      │
│                    ✓  ✓  ✓     Availability                      │
│                     ✓   ✓                                      │
│                      ✓✓✓                                       │
│                   Partition Tolerance                           │
│                  (Always required!)                             │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ System        | C | A | During Partition                       │
├─────────────────────────────────────────────────────────────────┤
│ etcd (CP)     | ✓ |   | Rejects writes if quorum lost           │
│ Cassandra (AP)|   | ✓ | Accepts writes, syncs later             │
│ MongoDB       | ~ | ~ | Depends on write concern (w=1 vs majority)│
└─────────────────────────────────────────────────────────────────┘

KEY EXPERIMENTS:
1. Normal Operations - All systems work, compare latency
2. Network Partition - CP fails, AP succeeds
3. Consistency Levels - Tune Cassandra R + W

REMEMBER:
- P is mandatory in distributed systems
- CP: Strong consistency, unavailable during partition
- AP: Always available, may return stale data
- Tunable: Balance via R + W > N (quorum)
    """)


async def main():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║          🎯 CAP Theorem Lab - Interactive Experiments            ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    print_summary()

    print("\n📋 Available Experiments:")
    print("  1. Normal Operations (baseline)")
    print("  2. Network Partition Simulation")
    print("  3. Consistency Levels Comparison")
    print("  4. Run All")
    print("  5. Exit")

    client = CAPLabClient()

    while True:
        choice = input("\nSelect experiment (1-5): ").strip()

        if choice == "1":
            await experiment_1_normal_operations(client)
        elif choice == "2":
            await experiment_2_partition_simulation(client)
        elif choice == "3":
            await experiment_3_consistency_levels(client)
        elif choice == "4":
            await experiment_1_normal_operations(client)
            await experiment_2_partition_simulation(client)
            await experiment_3_consistency_levels(client)
        elif choice == "5":
            print("\n👋 Thanks for learning about CAP!")
            break
        else:
            print("Invalid choice. Select 1-5.")


if __name__ == "__main__":
    asyncio.run(main())
