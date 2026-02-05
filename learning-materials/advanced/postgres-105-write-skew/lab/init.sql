-- Write Skew Lab - Ticket Booking System
-- Demonstrates write skew anomaly under REPEATABLE READ

CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    total_tickets INT NOT NULL,
    sold_tickets INT NOT NULL DEFAULT 0,
    CHECK (sold_tickets <= total_tickets)
);

-- Create an event with 100 tickets
INSERT INTO events (id, name, total_tickets, sold_tickets) VALUES
    (1, 'Concert', 100, 0);

-- Enable monitoring
CREATE TABLE check_results (
    run_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    transaction_a_sold INT,
    transaction_b_sold INT,
    total_sold INT,
    oversold BOOLEAN,
    isolation_level TEXT
);

-- Function to book tickets (demonstrates write skew)
CREATE OR REPLACE FUNCTION book_tickets(event_id INT, quantity INT)
RETURNS BOOLEAN AS $$
DECLARE
    available INT;
BEGIN
    -- Check availability (snapshot is taken here!)
    SELECT total_tickets - sold_tickets INTO available
    FROM events WHERE id = event_id;

    IF available >= quantity THEN
        -- Simulate processing delay
        PERFORM pg_sleep(0.2);

        -- Book tickets
        UPDATE events
        SET sold_tickets = sold_tickets + quantity
        WHERE id = event_id;

        RETURN TRUE;
    ELSE
        RAISE EXCEPTION 'Not enough tickets';
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Correct version using SERIALIZABLE
CREATE OR REPLACE FUNCTION book_tickets_safe(event_id INT, quantity INT)
RETURNS BOOLEAN AS $$
DECLARE
    available INT;
BEGIN
    -- Set SERIALIZABLE isolation
    SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;

    -- Check availability
    SELECT total_tickets - sold_tickets INTO available
    FROM events WHERE id = event_id FOR UPDATE;

    IF available >= quantity THEN
        -- Book tickets
        UPDATE events
        SET sold_tickets = sold_tickets + quantity
        WHERE id = event_id;

        RETURN TRUE;
    ELSE
        RAISE EXCEPTION 'Not enough tickets';
    END IF;
END;
$$ LANGUAGE plpgsql;
