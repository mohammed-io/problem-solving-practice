#!/usr/bin/env python3
"""
Cache Stampede Lab - Experiment Client

Demonstrates cache stampede and mitigation strategies.
"""

import asyncio
import time
import random
import redis
from datetime import datetime
from threading import Thread, Lock


# Simulated expensive computation
def expensive_computation(key):
    """Simulates a slow database query or API call."""
    print(f"  💭 Computing {key}...")
    time.sleep(2)  # Simulate 2-second computation
    result = f"data_{key}_{time.time()}"
    print(f"  ✓ Computed {key}: {result}")
    return result


# ============================================
# STRATEGY 1: No Caching (Baseline)
# ============================================
def no_cache_concurrent(key, num_clients=5):
    """All clients compute independently."""
    print("\n🔴 Strategy 1: No Caching (Stampede!)")
    print("="*40)

    start = time.time()
    threads = []

    def client(client_id):
        result = expensive_computation(key)
        elapsed = time.time() - start
        print(f"  Client {client_id}: {result} ({elapsed:.1f}s)")

    for i in range(num_clients):
        t = Thread(target=client, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    elapsed = time.time() - start
    print(f"\n  ⏱ Total time: {elapsed:.1f}s")
    print(f"  📊 Computation ran: {num_clients} times (stampede!)")


# ============================================
# STRATEGY 2: Naive Caching (Race Condition)
# ============================================
def naive_cache_concurrent(key, num_clients=5):
    """All clients check cache, miss, and compute together."""
    print("\n🟡 Strategy 2: Naive Caching (Race Condition)")
    print("="*40)

    r = redis.Redis(host='redis', port=6379, decode_responses=True)
    r.delete(key)  # Clear cache

    start = time.time()
    lock = Lock()
    results = []

    def client(client_id):
        # Check cache
        cached = r.get(key)
        if cached:
            print(f"  Client {client_id}: ✓ CACHE HIT")
            return

        print(f"  Client {client_id}: ✗ CACHE MISS")

        # Compute (all do this concurrently!)
        result = expensive_computation(key)

        # Set cache (might overwrite)
        r.setex(key, 10, result)
        results.append(result)

    threads = []
    for i in range(num_clients):
        t = Thread(target=client, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    elapsed = time.time() - start
    print(f"\n  ⏱ Total time: {elapsed:.1f}s")
    print(f"  📊 Computation ran: {len(results)} times")
    if len(results) > 1:
        print(f"  🚨 Stampede! {len(results)} clients computed together")


# ============================================
# STRATEGY 3: Lock-Based (Single Flyer)
# ============================================
def lock_cache_concurrent(key, num_clients=5):
    """First client gets lock, computes; others wait."""
    print("\n🟢 Strategy 3: Lock-Based (Single Flyer)")
    print("="*40)

    r = redis.Redis(host='redis', port=6379, decode_responses=True)
    r.delete(key)
    r.delete(f"{key}:lock")

    start = time.time()
    results = []

    def client(client_id):
        # Check cache
        cached = r.get(key)
        if cached:
            print(f"  Client {client_id}: ✓ CACHE HIT")
            return

        print(f"  Client {client_id}: ✗ CACHE MISS")

        # Try to acquire lock
        lock_key = f"{key}:lock"
        acquired = r.set(lock_key, "locked", nx=True, ex=10)

        if acquired:
            print(f"  Client {client_id}: 🔒 Got lock, computing...")
            try:
                result = expensive_computation(key)
                r.setex(key, 10, result)
                results.append(result)
            finally:
                r.delete(lock_key)
        else:
            # Wait for cache to be populated
            print(f"  Client {client_id}: ⏳ Waiting for cache...")
            for _ in range(20):  # Wait up to 2 seconds
                time.sleep(0.1)
                cached = r.get(key)
                if cached:
                    print(f"  Client {client_id}: ✓ Got from cache")
                    return
            print(f"  Client {client_id}: ⚠ Timeout, computing anyway...")
            result = expensive_computation(key)

    threads = []
    for i in range(num_clients):
        t = Thread(target=client, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    elapsed = time.time() - start
    print(f"\n  ⏱ Total time: {elapsed:.1f}s")
    print(f"  📊 Computation ran: {len(results)} time(s)")
    if len(results) == 1:
        print(f"  ✅ Single flyer! Stampede prevented")


# ============================================
# STRATEGY 4: Early Expiration (Probabilistic)
# ============================================
def early_expiration_concurrent(key, num_clients=5):
    """Cache expires slightly early for one client to refresh."""
    print("\n🔵 Strategy 4: Early Expiration (Probabilistic)")
    print("="*40)

    r = redis.Redis(host='redis', port=6379, decode_responses=True)
    r.delete(key)

    # Pre-populate cache with short TTL
    r.setex(key, 2, "initial_value")

    start = time.time()
    results = []

    def client(client_id):
        cached = r.get(key)
        if cached:
            print(f"  Client {client_id}: ✓ CACHE HIT")
            return

        print(f"  Client {client_id}: ✗ CACHE MISS")
        result = expensive_computation(key)
        r.setex(key, 5, result)  # 5 second TTL
        results.append(result)

    # Wait for cache to expire, then trigger all clients
    print("  Waiting for cache to expire...")
    time.sleep(2.5)

    threads = []
    for i in range(num_clients):
        t = Thread(target=client, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    elapsed = time.time() - start
    print(f"\n  ⏱ Total time: {elapsed:.1f}s")
    print(f"  📊 Computation ran: {len(results)} time(s)")


# ============================================
# STRATEGY 5: Request Coalescing
# ============================================
def request_coalescing_concurrent(key, num_clients=5):
    """Multiple waiting requests share a single computation."""
    print("\n🟣 Strategy 5: Request Coalescing")
    print("="*40)

    r = redis.Redis(host='redis', port=6379, decode_responses=True)
    r.delete(key)
    r.delete(f"{key}:computing")
    r.delete(f"{key}:result")

    start = time.time()
    computations = 0

    def client(client_id):
        # Check cache
        cached = r.get(key)
        if cached:
            print(f"  Client {client_id}: ✓ CACHE HIT")
            return

        # Check if someone is computing
        computing = r.get(f"{key}:computing")
        result_key = f"{key}:result"

        if computing:
            print(f"  Client {client_id}: ⏳ Waiting for computation...")
            # Wait for result (up to 3 seconds)
            for _ in range(30):
                result = r.get(result_key)
                if result:
                    r.setex(key, 10, result)
                    print(f"  Client {client_id}: ✓ Got coalesced result")
                    return
                time.sleep(0.1)
            print(f"  Client {client_id}: ⚠ Timeout")
            return

        # Mark as computing
        r.setex(f"{key}:computing", 5, "1")

        # Check race condition
        result = r.get(result_key)
        if result:
            # Someone else finished first
            print(f"  Client {client_id}: ✓ Another client finished first")
            r.setex(key, 10, result)
            return

        print(f"  Client {client_id}: 🔒 Computing...")

        # Compute and store
        result = expensive_computation(key)
        r.setex(result_key, 5, result)  # Store intermediate result
        r.setex(key, 10, result)  # Store cached value
        r.delete(f"{key}:computing")

        nonlocal computations
        computations += 1

    threads = []
    for i in range(num_clients):
        t = Thread(target=client, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    elapsed = time.time() - start
    print(f"\n  ⏱ Total time: {elapsed:.1f}s")
    print(f"  📊 Computation ran: {computations} time(s)")
    if computations == 1:
        print(f"  ✅ Perfect coalescing!")


def main():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                  💨 Cache Stampede Lab - Interactive                ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    # Wait for Redis
    time.sleep(1)

    key = "expensive_data"

    while True:
        print("\n📋 Available Strategies:")
        print("  1. No Caching (Baseline - causes stampede)")
        print("  2. Naive Caching (Race condition - still stampede)")
        print("  3. Lock-Based (Single flyer - prevents stampede)")
        print("  4. Early Expiration (Probabilistic refresh)")
        print("  5. Request Coalescing (Share computation)")
        print("  6. Compare All")
        print("  7. Exit")

        choice = input("\nSelect strategy (1-7): ").strip()

        if choice == "1":
            no_cache_concurrent(key)
        elif choice == "2":
            naive_cache_concurrent(key)
        elif choice == "3":
            lock_cache_concurrent(key)
        elif choice == "4":
            early_expiration_concurrent(key)
        elif choice == "5":
            request_coalescing_concurrent(key)
        elif choice == "6":
            print("\n🔬 Running comparison (all strategies)...")
            print("\n" + "="*60)
            no_cache_concurrent(key)
            time.sleep(1)
            naive_cache_concurrent(key)
            time.sleep(1)
            lock_cache_concurrent(key)
            time.sleep(1)
            early_expiration_concurrent(key)
            time.sleep(1)
            request_coalescing_concurrent(key)
        elif choice == "7":
            print("\n👋 Thanks for learning about cache stampede!")
            break
        else:
            print("Invalid choice")


if __name__ == "__main__":
    main()
