---
name: incident-016-slow-log
description: Excessive logging causing I/O bottleneck
difficulty: Intermediate
category: Performance / I/O
level: Staff Engineer
---
# Incident 016: The Logging Trap

---

## The Situation

Your team runs a real-time bidding system for online advertising:

**Requirements:**
- Process bid requests within 50ms (auction deadline)
- Handle 100,000 requests/second
- Log all bids for analytics and debugging

**Architecture:**
```
┌────────────────────────────────────────────────────────────┐
│                     API Gateway                            │
│                  100,000 req/second                        │
└────────────────────────┬───────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│                  Bid Processing Service                    │
│                  (Go microservice)                         │
│                  100 instances                             │
└────────────────────────┬───────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│                  Redis (bid cache)                         │
│                  PostgreSQL (analytics DB)                 │
└────────────────────────────────────────────────────────────┘
```

---

## The Incident Report

```
Time: Friday, 2:00 PM UTC - Peak ad bidding hours

Issue: Bids taking 200-500ms instead of normal 20-30ms
Impact: Missing auction deadlines, losing revenue
Severity: P0 (revenue critical)

Recent change: Added detailed logging for debugging
```

---

## What You See

### Latency Graph (P99)

```
Latency (ms)

500 │                                      ╭──────
    │                                 ╭────╯
400 │                            ╭────╯
    │                       ╭────╯
300 │                  ╭────╯
    │             ╭────╯
200 │        ╭────╯
    │   ╭────╯
 50 │───╯
    │
 20 │─── (normal baseline)
    └─┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────
      13:00 13:15 13:30 13:45 14:00 14:15 14:30 14:45 15:00
                                        ↑
                                    Logging deployed
```

### CPU Profile

```
Before deployment (13:45):
  runtime: 15%
  bid processing: 70%
  network I/O: 10%
  logging: 5%

After deployment (14:15):
  runtime: 15%
  bid processing: 35%
  network I/O: 10%
  logging: 50%  ← 10x increase!
```

### Disk I/O

```
Instance disk write rate:

Before: 5 MB/s
After:  250 MB/s  ← 50x increase!
```

### The Code That Changed

```go
// BEFORE (simple logging)
func ProcessBid(bid Bid) error {
    start := time.Now()

    // Process bid
    result := evaluateBid(bid)

    // Simple log
    log.Printf("Bid processed: user=%d, auction=%d, won=%v, duration=%s",
        bid.UserID, bid.AuctionID, result.Won, time.Since(start))

    return nil
}
```

```go
// AFTER (detailed logging deployed at 14:00)
func ProcessBid(bid Bid) error {
    start := time.Now()

    // Process bid
    result := evaluateBid(bid)

    // Detailed logging - EVERYTHING
    log.Printf("BID_PROCESSING_START user_id=%d auction_id=%d", bid.UserID, bid.AuctionID)
    log.Printf("BID_AMOUNT amount=%f currency=%s", bid.Amount, bid.Currency)
    log.Printf("BID_CONTEXT device=%s os=%s browser=%s", bid.Device, bid.OS, bid.Browser)
    log.Printf("BID_GEO country=%s region=%s city=%s", bid.Country, bid.Region, bid.City)
    log.Printf("BID_TIMING start_time=%s", start.Format(time.RFC3339Nano))
    log.Printf("BID_EVALUATION algorithm=%s version=%s", result.Algorithm, result.Version)
    log.Printf("BID_COMPETITORS count=%d avg_bid=%f", result.CompetitorCount, result.AvgCompetitorBid)
    log.Printf("BID_RESULT won=%v final_price=%f margin=%f", result.Won, result.FinalPrice, result.Margin)
    log.Printf("BID_DURATION duration_ms=%d", time.Since(start).Milliseconds())

    // Also log to file for offline analysis
    writeToFile(bid, result)

    return nil
}
```

---

## Analysis

**Before:** 1 log line per request
**After:** 10 log lines per request + file write

**At 100,000 req/second:**
- Before: 100,000 log lines/second
- After: 1,000,000 log lines/second + 100,000 file writes

---

## What is Synchronous I/O?

Imagine you're writing a letter.

**Synchronous:** You write, then walk to mailbox, then mail it, then walk back. Next letter.

**Asynchronous:** You write letters all day, someone else picks them up and mails them.

In code:
```go
// Synchronous blocking
log.Printf("...")  // Waits for write to complete before continuing

// Asynchronous non-blocking
go log.Printf("...")  // Returns immediately, write happens in background
```

**The problem:** `log.Printf` in Go is **synchronous by default**. It waits for the write to complete.

---

## Why is Logging Slow?

1. **Syslog writes:** Each log.Printf → write to /var/log → syslog daemon → disk
2. **Disk I/O is slow:** Even SSDs are slower than RAM
3. **Contention:** 100 instances all writing to shared disk
4. **Format string parsing:** Printf-style formatting has overhead

**Result:** CPU time wasted on I/O instead of bid processing.

---

## Jargon

| Term | Definition |
|------|------------|
| **Synchronous I/O** | Operation blocks until complete; program waits for disk/network |
| **Asynchronous I/O** | Operation returns immediately; actual I/O happens in background |
| **Syslog** | Unix logging system; centralized log daemon |
| **Standard output** | File descriptor 1 (stdout); where log.Printf writes by default |
| **Buffered I/O** | Writing to memory buffer, flushed to disk periodically |
| **Blocking call** | Function that doesn't return until operation completes |
| **Non-blocking call** | Function returns immediately, operation continues in background |
| **Structured logging** | JSON or key=value logging, easier to parse and query |

---

## Questions

1. **Why does synchronous logging hurt latency?** (Think about blocking)

2. **What's the difference between log.Printf and a proper logging library?**

3. **How can you log asynchronously without losing logs on crashes?**

4. **As a Staff Engineer, how do you design logging that's detailed but performant?**

---

**When you've thought about it, read `step-01.md`**
