-- Deadlock Lab - Database Schema
-- This schema creates the classic deadlock scenario

CREATE TABLE accounts (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    balance DECIMAL(10, 2) NOT NULL DEFAULT 1000.00,
    version INT DEFAULT 0
);

-- Seed data: 4 accounts with equal balances
INSERT INTO accounts (id, name, balance) VALUES
    (1, 'Alice', 1000.00),
    (2, 'Bob', 1000.00),
    (3, 'Charlie', 1000.00),
    (4, 'Diana', 1000.00);

-- Enable statement logging to observe locks
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_min_duration_statement = 0;

-- View to check for deadlocks
CREATE VIEW deadlock_stats AS
SELECT
    datname,
    deadlocks,
    xact_commit,
    xact_rollback,
    conflicts
FROM pg_stat_database
WHERE datname = 'payments';

-- Function to simulate payment (causes deadlock)
CREATE OR REPLACE FUNCTION transfer_money(
    from_account INT,
    to_account INT,
    amount DECIMAL
) RETURNS BOOLEAN AS $$
BEGIN
    -- Lock sender
    UPDATE accounts SET balance = balance - amount WHERE id = from_account;

    -- Simulate processing delay (increases deadlock probability)
    PERFORM pg_sleep(0.1);

    -- Lock receiver
    UPDATE accounts SET balance = balance + amount WHERE id = to_account;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;
