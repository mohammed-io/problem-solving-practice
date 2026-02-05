#!/usr/bin/env python3
"""
Distributed Lease & Leader Election Lab

Demonstrates lease expiration and leader election.
"""

import time
import etcd3
import redis
from datetime import datetime


class LeaseLab:
    def __init__(self):
        self.etcd = etcd3.client(host="lease-etcd1", port=2379)
        self.redis = redis.Redis(host="lease-redis", port=6379, decode_responses=True)


# ============================================
# STRATEGY 1: etcd Leases (Robust)
# ============================================
def etcd_lease_demo(lab):
    """etcd lease with automatic expiration and renewal."""
    print("\n" + "="*50)
    print("STRATEGY 1: etcd Leases")
    print("="*50)

    # Create a lease
    lease = lab.etcd.lease("my-lease", ttl=5)

    try:
        print("\n🔒 Acquiring lease (5s TTL)...")
        lease.refresh()
        print("  ✓ Lease acquired")

        # Hold lease and refresh
        for i in range(3):
            time.sleep(2)
            lease.refresh()
            print(f"  ✓ Lease refreshed ({i+1}/3)")

        print("\n  ✓ Lease held successfully")

    except Exception as e:
        print(f"  ✗ Lease failed: {e}")


# ============================================
# STRATEGY 2: Redis Leases (Simple)
# ============================================
def redis_lease_demo(lab):
    """Redis-based lease with SET NX EX."""
    print("\n" + "="*50)
    print("STRATEGY 2: Redis Leases")
    print("="*50)

    lock_key = "my-lock"
    lock_value = "holder-1"

    # Try to acquire lock
    acquired = lab.redis.set(lock_key, lock_value, nx=True, ex=5)

    if acquired:
        print(f"\n🔒 Lock acquired: {lock_key}")
        print("  Holding for 3 seconds...")

        for i in range(3):
            time.sleep(1)
            # Refresh lock
            ttl = lab.redis.ttl(lock_key)
            if ttl > 2:  # Refresh if more than 2s left
                lab.redis.expire(lock_key, 5)
                print(f"  ✓ Refreshed (TTL was {ttl}s)")

        # Release lock
        lab.redis.delete(lock_key)
        print("  ✓ Lock released")
    else:
        print(f"\n  ✗ Could not acquire lock (held by: {lab.redis.get(lock_key)})")


# ============================================
# STRATEGY 3: Leader Election
# ============================================
def leader_election_demo(lab):
    """Simple leader election using etcd."""
    print("\n" + "="*50)
    print("STRATEGY 3: Leader Election")
    print("="*50)

    election_key = "/election/leader"

    # Try to become leader
    print("\n🏆 Attempting to become leader...")

    # Campaign for leadership
    campaign = lab.etcd.election(election_key, ttl=10)

    try:
        print("  Campaigning for leadership...")

        # Wait to see if we become leader
        events = campaign.events()

        start = time.time()
        leader_id = None

        for event in events:
            if event.is_put:
                leader_id = event.key.decode().split("/")[-1]
                if leader_id == campaign.id:
                    print(f"  🏆 I became leader! (ID: {leader_id[:8]})")
                    break
                else:
                    print(f"  👑 Current leader: {leader_id[:8]}")
                    print("  ⏳ Waiting for leadership change...")
                    break

    except Exception as e:
        print(f"  ✗ Election failed: {e}")


# ============================================
# EXPERIMENT: Lease Expiration
# ============================================
def experiment_lease_expiration(lab):
    """Demonstrate what happens when lease expires."""
    print("\n" + "="*50)
    print("EXPERIMENT: Lease Expiration Scenario")
    print("="*50)

    print("\nScenario: Client acquires lease, crashes, lease expires")
    print("  Expected: Another client can acquire after TTL")

    # Client 1 acquires
    print("\n[Client 1] Acquiring lease (5s TTL)...")
    lease = lab.etcd.lease("service-lock", ttl=5)
    lease.refresh()
    print("  ✓ Lease acquired by Client 1")

    # Simulate crash - don't refresh
    print("\n[Client 1] 💥 Simulating crash (no refresh)...")

    print("\n[Client 2] Trying to acquire lease...")
    for i in range(7):
        try:
            lease2 = lab.etcd.lease("service-lock", ttl=5)
            lease2.refresh()
            print(f"  ✓ Lease acquired by Client 2 (after {i}s wait)")
            break
        except Exception:
            print(f"  ✗ Still held by Client 1 ({i}s)")
            time.sleep(1)


def experiment_contended_leases(lab):
    """Multiple clients contending for same lease."""
    print("\n" + "="*50)
    print("EXPERIMENT: Contended Leases")
    print("="*50)

    print("\nSimulating 3 clients trying to acquire same lease...")

    lock_key = "contended-lock"

    def try_acquire(client_id, lab):
        for attempt in range(10):
            result = lab.redis.set(lock_key, f"client-{client_id}", nx=True, ex=3)
            if result:
                print(f"  ✓ Client {client_id}: ACQUIRED lease!")
                time.sleep(2)
                lab.redis.delete(lock_key)
                print(f"  ✓ Client {client_id}: Released")
                return
            else:
                current = lab.redis.get(lock_key)
                print(f"  ✗ Client {client_id}: Held by {current}")
                time.sleep(0.5)

    import threading
    threads = []
    for i in range(3):
        t = threading.Thread(target=try_acquire, args=(i+1, lab))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()


def main():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║             🔐 Distributed Lease Lab - Interactive               ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    lab = LeaseLab()
    time.sleep(2)

    while True:
        print("\n📋 Available Experiments:")
        print("  1. etcd Leases (Robust)")
        print("  2. Redis Leases (Simple)")
        print("  3. Leader Election")
        print("  4. Lease Expiration Scenario")
        print("  5. Contended Leases (3 clients)")
        print("  6. Exit")

        choice = input("\nSelect experiment (1-6): ").strip()

        if choice == "1":
            etcd_lease_demo(lab)
        elif choice == "2":
            redis_lease_demo(lab)
        elif choice == "3":
            leader_election_demo(lab)
        elif choice == "4":
            experiment_lease_expiration(lab)
        elif choice == "5":
            experiment_contended_leases(lab)
        elif choice == "6":
            print("\n👋 Thanks for learning about distributed leases!")
            break
        else:
            print("Invalid choice")


if __name__ == "__main__":
    main()
