# Step 1: Understanding TIME_WAIT

---

## Why TIME_WAIT Exists

```
Purpose 1: Ensure final ACK received
  A → B: FIN
  A ← B: ACK
  A ← B: FIN
  A → B: ACK

  If A's last ACK is lost, B retransmits FIN
  A must be in TIME_WAIT to receive and respond

Purpose 2: Prevent delayed packets
  Old packet from previous connection arrives
  If new connection uses same ports → confusion
  TIME_WAIT ensures ports unused long enough
```

---

## Port Exhaustion Math

```
Ephemeral port range: 32768-60999 = ~28K ports
TIME_WAIT duration: 60 seconds

Connections per second possible = 28000 / 60 = 466 QPS
Without connection pooling: >466 QPS = port exhaustion!

With 10,000 QPS:
  Need 10,000 × 60 = 600,000 ports
  Only have 28,000
  Result: Exhaustion
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's TIME_WAIT state? (Socket state after closing, ensures final ACK received and prevents delayed packets)
2. What's the duration of TIME_WAIT? (60 seconds - 2×MSL)
3. What's the ephemeral port range? (32768-60999, about 28K ports)
4. What's port exhaustion math? (28000 ports / 60 seconds = ~466 connections/second max)
5. Why does TIME_WAIT exist? (Ensure final ACK received, prevent delayed packets from old connections)

---

**Read `step-02.md`
