#!/usr/bin/env python3
"""
Replica Lag Lab - Experiment Client

Demonstrates replica lag and its effects.
"""

import time
import subprocess
import psycopg
from datetime import datetime


class ReplicaLagLab:
    def __init__(self):
        self.primary = "primary"
        self.replica1 = "replica1"
        self.replica2 = "replica2"
        self.conn_params = {
            "dbname": "appdb", "user": "admin", "password": "secret"
        }

    def query(self, host, sql):
        """Execute query on specified host."""
        conn = psycopg.connect(host=host, port=5432, **self.conn_params)
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                if sql.strip().upper().startswith("SELECT"):
                    return cur.fetchall()
                conn.commit()
                return None
        finally:
            conn.close()

    def get_lag(self, replica_host):
        """Get replica lag from primary's perspective."""
        try:
            result = self.query(
                self.primary,
                f"""
                SELECT client_addr, state, sync_state, sync_offset_lag_bytes
                FROM pg_stat_replication
                WHERE application_name LIKE '%{replica_host}%'
                """
            )
            return result[0] if result else None
        except Exception as e:
            return None

    def insert_order(self, amount):
        """Insert an order on primary."""
        self.query(
            self.primary,
            f"INSERT INTO orders (amount) VALUES ({amount})"
        )

    def get_count(self, host):
        """Get order count from specified host."""
        result = self.query(host, "SELECT COUNT(*) FROM orders")
        return result[0][0] if result else 0

    def show_status(self):
        """Show replication status."""
        print("\n📊 Replication Status:")
        print("-" * 50)

        for name, host in [("Primary", self.primary), ("Replica 1", self.replica1), ("Replica 2", self.replica2)]:
            try:
                count = self.get_count(host)
                print(f"  {name:12} | Orders: {count}")
            except:
                print(f"  {name:12} | Orders: Not connected")

        print("\n📈 Replication Lag:")
        for host in [self.replica1, self.replica2]:
            lag = self.get_lag(host)
            if lag:
                state, sync_state = lag[1], lag[2]
                print(f"  {host}: State={state}, Sync={sync_state}")
            else:
                print(f"  {host}: No replication info")


def experiment_1_basic_replication(lab):
    """Experiment 1: Basic replication demonstration."""
    print("\n" + "="*60)
    print("EXPERIMENT 1: Basic Streaming Replication")
    print("="*60)

    lab.show_status()

    print("\n📝 Inserting orders on primary...")
    for i in range(5):
        lab.insert_order(100 + i)
        print(f"  Inserted order {i+1}")
        time.sleep(0.5)

    print("\n⏳ Waiting for replication...")
    time.sleep(2)

    lab.show_status()


def experiment_2_measure_lag(lab):
    """Experiment 2: Measure replication lag."""
    print("\n" + "="*60)
    print("EXPERIMENT 2: Measuring Replication Lag")
    print("="*60)

    print("\n📝 Rapid inserts on primary...")
    start = time.time()

    for i in range(10):
        lab.insert_order(i)
        time.sleep(0.1)

    print(f"\n⏱ Inserted 10 orders in {time.time()-start:.1f}s")

    print("\n📊 Check replica counts immediately:")
    p_count = lab.get_count(lab.primary)
    r1_count = lab.get_count(lab.replica1)
    r2_count = lab.get_count(lab.replica2)

    print(f"  Primary:  {p_count} orders")
    print(f"  Replica 1: {r1_count} orders (lag: {p_count - r1_count})")
    print(f"  Replica 2: {r2_count} orders (lag: {p_count - r2_count})")

    print("\n⏳ Waiting for catch up...")
    time.sleep(3)

    print("\n📊 After waiting:")
    r1_count = lab.get_count(lab.replica1)
    r2_count = lab.get_count(lab.replica2)
    print(f"  Replica 1: {r1_count} orders")
    print(f"  Replica 2: {r2_count} orders")


def experiment_3_network_partition(lab):
    """Experiment 3: Simulate network partition."""
    print("\n" + "="*60)
    print("EXPERIMENT 3: Network Partition Simulation")
    print("="*60)
    print("\nACTION: In another terminal, run:")
    print("  docker pause replica-lag-replica1")
    print("\nPress Enter when ready...")
    input()

    print("\n📝 Inserting orders while partitioned...")
    for i in range(5):
        lab.insert_order(i)
        print(f"  Inserted order {i+1}")

    print("\n📊 Status during partition:")
    lab.show_status()

    print("\nACTION: Restore with: docker unpause replica-lag-replica1")
    print("Press Enter when ready...")
    input()

    print("\n⏳ Waiting for recovery...")
    time.sleep(3)
    lab.show_status()


def experiment_4_lag_monitoring(lab):
    """Experiment 4: Monitor lag over time."""
    print("\n" + "="*60)
    print("EXPERIMENT 4: Continuous Lag Monitoring")
    print("="*60)
    print("\nMonitoring for 10 seconds. Press Ctrl+C to stop early.")

    try:
        for i in range(10):
            lab.insert_order(i)
            p_count = lab.get_count(lab.primary)
            r1_count = lab.get_count(lab.replica1)
            lag = p_count - r1_count
            print(f"[{i}] Primary: {p_count}, Replica1: {r1_count}, Lag: {lag}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n⏹ Monitoring stopped")


def main():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                 📊 Replica Lag Lab - Interactive                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    print("⚠️  Note: This lab requires manual setup of replica servers.")
    print("    For a production-ready replica lag lab, use Patroni or pg_auto.")

    lab = ReplicaLagLab()
    time.sleep(2)

    while True:
        print("\n📋 Available Experiments:")
        print("  1. Basic Replication")
        print("  2. Measure Lag")
        print("  3. Network Partition (manual)")
        print("  4. Continuous Monitoring")
        print("  5. Show Status")
        print("  6. Exit")

        choice = input("\nSelect experiment (1-6): ").strip()

        if choice == "1":
            experiment_1_basic_replication(lab)
        elif choice == "2":
            experiment_2_measure_lag(lab)
        elif choice == "3":
            experiment_3_network_partition(lab)
        elif choice == "4":
            experiment_4_lag_monitoring(lab)
        elif choice == "5":
            lab.show_status()
        elif choice == "6":
            print("\n👋 Thanks for learning about replica lag!")
            break
        else:
            print("Invalid choice")


if __name__ == "__main__":
    main()
