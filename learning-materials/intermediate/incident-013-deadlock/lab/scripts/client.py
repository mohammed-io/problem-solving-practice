#!/usr/bin/env python3
"""
Deadlock Lab - Experiment Client

Demonstrates database deadlocks and solutions.
"""

import asyncio
import threading
import time
import psycopg
from datetime import datetime


class DeadlockLab:
    def __init__(self, host="postgres", port=5432, database="payments",
                 user="admin", password="secret"):
        self.conn_params = {
            "host": host, "port": port, "dbname": database,
            "user": user, "password": password, "autocommit": False
        }

    def get_balance(self, account_id):
        """Get account balance."""
        with psycopg.connect(**self.conn_params) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT balance FROM accounts WHERE id = %s", (account_id,))
                return cur.fetchone()[0]

    def transfer_locking_wrong_order(self, from_id, to_id, amount, delay=0.1):
        """
        Transfer WITHOUT lock ordering - CAUSES DEADLOCK

        Transaction A: Lock 1 → wait for 2 → DEADLOCK
        Transaction B: Lock 2 → wait for 1 → DEADLOCK
        """
        try:
            with psycopg.connect(**self.conn_params) as conn:
                conn.isolation_level = psycopg.IsolationLevel.READ_COMMITTED
                with conn.cursor() as cur:
                    # Lock from_account (e.g., account 1)
                    cur.execute(
                        "UPDATE accounts SET balance = balance - %s WHERE id = %s",
                        (amount, from_id)
                    )
                    print(f"  [Tx] Locked account {from_id}")

                    # Delay to ensure deadlock condition
                    time.sleep(delay)

                    # Lock to_account (e.g., account 2) - may deadlock!
                    cur.execute(
                        "UPDATE accounts SET balance = balance + %s WHERE id = %s",
                        (amount, to_id)
                    )
                    print(f"  [Tx] Locked account {to_id}")

                conn.commit()
                print(f"  ✓ Transfer: {from_id} → {to_id}: ${amount}")
                return True

        except psycopg.OperationalError as e:
            if "deadlock" in str(e).lower():
                print(f"  ✗ DEADLOCK detected: {e}")
                return False
            raise

    def transfer_with_lock_ordering(self, from_id, to_id, amount):
        """
        Transfer WITH lock ordering - PREVENTS DEADLOCK

        Always lock lower ID first, regardless of transfer direction.
        """
        # Always lock in ID order
        first, second = sorted([from_id, to_id])

        try:
            with psycopg.connect(**self.conn_params) as conn:
                conn.isolation_level = psycopg.IsolationLevel.READ_COMMITTED
                with conn.cursor() as cur:
                    if from_id < to_id:
                        # Normal: debit from, credit to
                        cur.execute(
                            "UPDATE accounts SET balance = balance - %s WHERE id = %s",
                            (amount, from_id)
                        )
                        cur.execute(
                            "UPDATE accounts SET balance = balance + %s WHERE id = %s",
                            (amount, to_id)
                        )
                    else:
                        # Reverse: credit to first, debit from second
                        cur.execute(
                            "UPDATE accounts SET balance = balance + %s WHERE id = %s",
                            (amount, to_id)
                        )
                        cur.execute(
                            "UPDATE accounts SET balance = balance - %s WHERE id = %s",
                            (amount, from_id)
                        )

                conn.commit()
                print(f"  ✓ Transfer: {from_id} → {to_id}: ${amount}")
                return True

        except psycopg.OperationalError as e:
            if "deadlock" in str(e).lower():
                print(f"  ✗ DEADLOCK (unexpected!): {e}")
                return False
            raise

    def show_balances(self):
        """Display all account balances."""
        with psycopg.connect(**self.conn_params) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, balance FROM accounts ORDER BY id")
                print("\n💰 Current Balances:")
                print("  ID  | Name     | Balance")
                print("  ----|----------|--------")
                for row in cur.fetchall():
                    print(f"  {row[0]:3} | {row[1]:8} | ${row[2]:7.2f}")

    def get_deadlock_count(self):
        """Get deadlock statistics."""
        with psycopg.connect(**self.conn_params) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT deadlocks FROM pg_stat_database WHERE datname = 'payments'")
                return cur.fetchone()[0]


def experiment_1_induce_deadlock(lab):
    """Experiment 1: Induce a deadlock by concurrent transfers in opposite order."""
    print("\n" + "="*60)
    print("EXPERIMENT 1: Inducing Deadlock")
    print("="*60)
    print("\nScenario: Two concurrent transfers in opposite order")
    print("  Thread A: Transfer from account 1 → 2")
    print("  Thread B: Transfer from account 2 → 1")
    print("\nExpected: Both threads acquire locks in opposite order → DEADLOCK")

    lab.show_balances()

    def tx_a():
        lab.transfer_locking_wrong_order(1, 2, 100, delay=0.5)

    def tx_b():
        lab.transfer_locking_wrong_order(2, 1, 100, delay=0.5)

    # Run concurrent transactions
    thread_a = threading.Thread(target=tx_a)
    thread_b = threading.Thread(target=tx_b)

    print("\n🔄 Starting concurrent transactions...")
    thread_a.start()
    time.sleep(0.1)  # Ensure A locks first
    thread_b.start()

    thread_a.join()
    thread_b.join()

    print(f"\n📊 Deadlocks detected: {lab.get_deadlock_count()}")
    lab.show_balances()


def experiment_2_lock_ordering(lab):
    """Experiment 2: Fix deadlock using lock ordering."""
    print("\n" + "="*60)
    print("EXPERIMENT 2: Fix with Lock Ordering")
    print("="*60)
    print("\nSolution: Always lock accounts in ID order (1 before 2, etc.)")
    print("  Thread A: Transfer 1 → 2 (locks 1, then 2)")
    print("  Thread B: Transfer 2 → 1 (still locks 1, then 2!)")
    print("\nExpected: No deadlock, both succeed")

    def tx_a():
        lab.transfer_with_lock_ordering(1, 2, 100)

    def tx_b():
        lab.transfer_with_lock_ordering(2, 1, 100)

    # Run concurrent transactions
    thread_a = threading.Thread(target=tx_a)
    thread_b = threading.Thread(target=tx_b)

    print("\n🔄 Starting concurrent transactions...")
    thread_a.start()
    thread_b.start()

    thread_a.join()
    thread_b.join()

    print(f"\n📊 Deadlocks: {lab.get_deadlock_count()}")
    lab.show_balances()


def experiment_3_select_for_update(lab):
    """Experiment 3: Using SELECT FOR UPDATE with lock ordering."""
    print("\n" + "="*60)
    print("EXPERIMENT 3: SELECT FOR UPDATE Pattern")
    print("="*60)

    try:
        with psycopg.connect(**lab.conn_params) as conn:
            conn.isolation_level = psycopg.IsolationLevel.READ_COMMITTED
            with conn.cursor() as cur:
                # Lock both accounts in ID order
                accounts = sorted([1, 2])
                for acc_id in accounts:
                    cur.execute(
                        "SELECT balance FROM accounts WHERE id = %s FOR UPDATE",
                        (acc_id,)
                    )
                    print(f"  🔒 Locked account {acc_id}")

                # Check sufficient funds
                cur.execute("SELECT balance FROM accounts WHERE id = %s", (accounts[0],))
                balance = cur.fetchone()[0]

                if balance >= 100:
                    # Perform transfer
                    cur.execute(
                        "UPDATE accounts SET balance = balance - 100 WHERE id = %s",
                        (accounts[0],)
                    )
                    cur.execute(
                        "UPDATE accounts SET balance = balance + 100 WHERE id = %s",
                        (accounts[1],)
                    )
                    conn.commit()
                    print("  ✓ Transfer completed")
                else:
                    print("  ✗ Insufficient funds")
                    conn.rollback()

    except psycopg.Error as e:
        print(f"  ✗ Error: {e}")

    lab.show_balances()


def experiment_4_retry_logic(lab):
    """Experiment 4: Automatic retry on deadlock."""
    print("\n" + "="*60)
    print("EXPERIMENT 4: Automatic Retry Logic")
    print("="*60)
    print("\nSolution: Catch deadlock errors and retry with backoff")

    max_retries = 3

    for attempt in range(1, max_retries + 1):
        try:
            # Try the unsafe transfer
            success = lab.transfer_locking_wrong_order(1, 2, 100, delay=0.1)
            if success:
                print(f"  ✓ Success on attempt {attempt}")
                break
        except:
            print(f"  ✗ Attempt {attempt} failed, retrying...")
            time.sleep(0.1 * attempt)  # Exponential backoff

    lab.show_balances()


def main():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                  🔄 Deadlock Lab - Interactive                    ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    lab = DeadlockLab()

    # Wait for DB
    import time
    time.sleep(2)

    # Reset balances
    with psycopg.connect(**lab.conn_params) as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE accounts SET balance = 1000.00")

    while True:
        print("\n📋 Available Experiments:")
        print("  1. Induce Deadlock (opposite lock order)")
        print("  2. Fix with Lock Ordering")
        print("  3. SELECT FOR UPDATE Pattern")
        print("  4. Automatic Retry Logic")
        print("  5. Show Balances")
        print("  6. Reset Balances")
        print("  7. Exit")

        choice = input("\nSelect experiment (1-7): ").strip()

        if choice == "1":
            experiment_1_induce_deadlock(lab)
        elif choice == "2":
            experiment_2_lock_ordering(lab)
        elif choice == "3":
            experiment_3_select_for_update(lab)
        elif choice == "4":
            experiment_4_retry_logic(lab)
        elif choice == "5":
            lab.show_balances()
        elif choice == "6":
            with psycopg.connect(**lab.conn_params) as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE accounts SET balance = 1000.00")
            print("✓ Balances reset")
        elif choice == "7":
            print("\n👋 Thanks for learning about deadlocks!")
            break
        else:
            print("Invalid choice")


if __name__ == "__main__":
    main()
