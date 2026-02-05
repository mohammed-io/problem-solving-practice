#!/usr/bin/env python3
"""
Write Skew Lab - Experiment Client

Demonstrates write skew anomaly and how to prevent it.
"""

import asyncio
import threading
import time
import psycopg
from datetime import datetime


class WriteSkewLab:
    def __init__(self, host="postgres", port=5432, database="ticketshop",
                 user="admin", password="secret"):
        self.conn_params = {
            "host": host, "port": port, "dbname": database,
            "user": user, "password": password, "autocommit": False
        }

    def reset_event(self):
        """Reset event to initial state."""
        with psycopg.connect(**self.conn_params) as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE events SET sold_tickets = 0 WHERE id = 1")

    def get_status(self):
        """Get current event status."""
        with psycopg.connect(**self.conn_params) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT total_tickets, sold_tickets FROM events WHERE id = 1")
                total, sold = cur.fetchone()
                return total, sold

    def book_tickets_unsafe(self, quantity, delay=0.2):
        """
        Book tickets with REPEATABLE READ - VULNERABLE TO WRITE SKEW
        """
        try:
            with psycopg.connect(**self.conn_params) as conn:
                conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
                with conn.cursor() as cur:
                    # Check availability (snapshot taken here!)
                    cur.execute(
                        "SELECT total_tickets - sold_tickets FROM events WHERE id = %s",
                        (1,)
                    )
                    available = cur.fetchone()[0]
                    print(f"  [Tx] Available: {available} tickets")

                    if available >= quantity:
                        # Processing delay allows concurrent transaction
                        time.sleep(delay)

                        # Update may use stale snapshot!
                        cur.execute(
                            "UPDATE events SET sold_tickets = sold_tickets + %s WHERE id = %s",
                            (quantity, 1)
                        )
                        conn.commit()
                        print(f"  ✓ Booked {quantity} tickets")
                        return True
                    else:
                        print(f"  ✗ Sold out!")
                        return False

        except psycopg.OperationalError as e:
            if "serialization" in str(e).lower() or "deadlock" in str(e).lower():
                print(f"  ✗ Serialization failure: {e}")
                return False
            raise

    def book_tickets_safe(self, quantity):
        """
        Book tickets with SERIALIZABLE - PREVENTS WRITE SKEW
        Uses FOR UPDATE to lock the row.
        """
        try:
            with psycopg.connect(**self.conn_params) as conn:
                # Use SERIALIZABLE isolation
                conn.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
                with conn.cursor() as cur:
                    # Lock the row first
                    cur.execute(
                        "SELECT total_tickets - sold_tickets FROM events WHERE id = %s FOR UPDATE",
                        (1,)
                    )
                    available = cur.fetchone()[0]
                    print(f"  [Tx] Available: {available} tickets (locked)")

                    if available >= quantity:
                        time.sleep(0.1)  # Simulate processing
                        cur.execute(
                            "UPDATE events SET sold_tickets = sold_tickets + %s WHERE id = %s",
                            (quantity, 1)
                        )
                        conn.commit()
                        print(f"  ✓ Booked {quantity} tickets")
                        return True
                    else:
                        print(f"  ✗ Sold out!")
                        conn.rollback()
                        return False

        except psycopg.OperationalError as e:
            if "serialization" in str(e).lower():
                print(f"  ✗ Serialization failure (expected): {e}")
                return False
            raise

    def book_tickets_serializable(self, quantity):
        """
        Book using SERIALIZABLE with automatic retry.
        """
        max_retries = 5

        for attempt in range(1, max_retries + 1):
            try:
                with psycopg.connect(**self.conn_params) as conn:
                    conn.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT total_tickets - sold_tickets FROM events WHERE id = %s FOR UPDATE",
                            (1,)
                        )
                        available = cur.fetchone()[0]

                        if available >= quantity:
                            time.sleep(0.1)
                            cur.execute(
                                "UPDATE events SET sold_tickets = sold_tickets + %s WHERE id = %s",
                                (quantity, 1)
                            )
                            conn.commit()
                            print(f"  ✓ Booked {quantity} tickets (attempt {attempt})")
                            return True
                        else:
                            print(f"  ✗ Sold out!")
                            return False

            except psycopg.OperationalError as e:
                if "serialization" in str(e).lower() or "deadlock" in str(e).lower():
                    print(f"  ⚠ Retry {attempt}/{max_retries}: {e}")
                    time.sleep(0.1 * attempt)  # Exponential backoff
                    continue
                raise

        print(f"  ✗ Failed after {max_retries} attempts")
        return False


def experiment_1_write_skew(lab):
    """Experiment 1: Demonstrate write skew anomaly."""
    print("\n" + "="*60)
    print("EXPERIMENT 1: Write Skew Anomaly")
    print("="*60)
    print("\nScenario: Two users book tickets concurrently")
    print("  Total tickets: 100")
    print("  User A: Books 60 tickets")
    print("  User B: Books 50 tickets")
    print("\nExpected with REPEATABLE READ:")
    print("  Both see 100 available → Both succeed → 110 sold! 🚨")

    lab.reset_event()
    total, sold = lab.get_status()
    print(f"\n💰 Starting: {sold}/{total} sold")

    def user_a():
        print("\n[User A] Booking 60 tickets...")
        lab.book_tickets_unsafe(60, delay=0.3)

    def user_b():
        print("\n[User B] Booking 50 tickets...")
        lab.book_tickets_unsafe(50, delay=0.3)

    # Run concurrent
    thread_a = threading.Thread(target=user_a)
    thread_b = threading.Thread(target=user_b)

    thread_a.start()
    time.sleep(0.05)  # Slight offset for race
    thread_b.start()

    thread_a.join()
    thread_b.join()

    total, sold = lab.get_status()
    print(f"\n💰 Final: {sold}/{total} sold")
    if sold > total:
        print(f"  🚨 OVERSOLD by {sold - total} tickets! (Write skew anomaly)")
    else:
        print(f"  ✓ Within limit")


def experiment_2_serializable(lab):
    """Experiment 2: Fix with SERIALIZABLE isolation."""
    print("\n" + "="*60)
    print("EXPERIMENT 2: Fix with SERIALIZABLE Isolation")
    print("="*60)
    print("\nUsing SERIALIZABLE + FOR UPDATE prevents write skew")

    lab.reset_event()
    total, sold = lab.get_status()
    print(f"\n💰 Starting: {sold}/{total} sold")

    def user_a():
        print("\n[User A] Booking 60 tickets...")
        lab.book_tickets_serializable(60)

    def user_b():
        print("\n[User B] Booking 50 tickets...")
        lab.book_tickets_serializable(50)

    # Run concurrent
    thread_a = threading.Thread(target=user_a)
    thread_b = threading.Thread(target=user_b)

    thread_a.start()
    thread_b.start()

    thread_a.join()
    thread_b.join()

    total, sold = lab.get_status()
    print(f"\n💰 Final: {sold}/{total} sold")
    if sold > total:
        print(f"  🚨 OVERSOLD by {sold - total} tickets!")
    else:
        print(f"  ✓ Within limit (SERIALIZABLE prevented write skew)")


def experiment_3_comparison(lab):
    """Experiment 3: Compare isolation levels."""
    print("\n" + "="*60)
    print("EXPERIMENT 3: Isolation Level Comparison")
    print("="*60)

    print("\nTesting same workload with different isolation levels:")
    print("  REPEATABLE READ: Allows write skew (anomaly)")
    print("  SERIALIZABLE:     Prevents write skew (safe)")

    for iso_level in ["REPEATABLE_READ", "SERIALIZABLE"]:
        lab.reset_event()
        print(f"\n{'='*50}")
        print(f"Testing: {iso_level}")
        print('='*50)

        success_count = 0
        oversold_count = 0

        for run in range(3):
            lab.reset_event()

            def book_a():
                return lab.book_tickets_serializable(60) if iso_level == "SERIALIZABLE" else lab.book_tickets_unsafe(60)

            def book_b():
                return lab.book_tickets_serializable(50) if iso_level == "SERIALIZABLE" else lab.book_tickets_unsafe(50)

            t1 = threading.Thread(target=book_a)
            t2 = threading.Thread(target=book_b)

            t1.start()
            t2.start()
            t1.join()
            t2.join()

            total, sold = lab.get_status()
            if sold <= total:
                success_count += 1
            else:
                oversold_count += 1
            print(f"  Run {run+1}: {sold}/{total} {'✓' if sold <= total else '🚨'}")

        print(f"\n  Results: {success_count} safe, {oversold_count} oversold")


def main():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                  🎫 Write Skew Lab - Interactive                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    lab = WriteSkewLab()
    time.sleep(2)  # Wait for DB

    while True:
        print("\n📋 Available Experiments:")
        print("  1. Demonstrate Write Skew Anomaly")
        print("  2. Fix with SERIALIZABLE Isolation")
        print("  3. Compare Isolation Levels")
        print("  4. Show Status")
        print("  5. Reset Event")
        print("  6. Exit")

        choice = input("\nSelect experiment (1-6): ").strip()

        if choice == "1":
            experiment_1_write_skew(lab)
        elif choice == "2":
            experiment_2_serializable(lab)
        elif choice == "3":
            experiment_3_comparison(lab)
        elif choice == "4":
            total, sold = lab.get_status()
            print(f"\n💰 Current: {sold}/{total} tickets sold")
        elif choice == "5":
            lab.reset_event()
            print("✓ Event reset")
        elif choice == "6":
            print("\n👋 Thanks for learning about write skew!")
            break
        else:
            print("Invalid choice")


if __name__ == "__main__":
    main()
