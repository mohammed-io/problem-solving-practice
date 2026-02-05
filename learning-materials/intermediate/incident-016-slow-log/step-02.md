# Step 2: Understand the Solutions

---

## Solution Options

### Option 1: Use Buffered Asynchronous Logging

```go
import "go.uber.org/zap"

var logger *zap.Logger

func init() {
    logger, _ = zap.NewProduction()
    // Buffer in memory, flush to disk asynchronously
}

func ProcessBid(bid Bid) error {
    // Non-blocking structured logging
    logger.Info("bid_processed",
        zap.Int64("user_id", bid.UserID),
        zap.Int64("auction_id", bid.AuctionID),
        zap.Bool("won", result.Won),
        zap.Duration("duration", time.Since(start)),
    )
    return nil
}
```

**Pros:** Fast, non-blocking
**Cons:** Can lose logs on crash (if buffer not flushed)

### Option 2: Log Less, Not More

```go
// Only log errors and important events
func ProcessBid(bid Bid) error {
    start := time.Now()
    result := evaluateBid(bid)

    if result.Error != nil {
        // Always log errors
        logger.Error("bid_failed",
            zap.Int64("user_id", bid.UserID),
            zap.Error(result.Error),
        )
    } else if time.Since(start) > 100*time.Millisecond {
        // Log slow bids (for monitoring)
        logger.Warn("bid_slow",
            zap.Int64("user_id", bid.UserID),
            zap.Duration("duration", time.Since(start)),
        )
    }
    // Normal bids: no log (or sample 1%)

    return nil
}
```

**Pros:** Minimal overhead
**Cons:** Less debugging information

### Option 3: Sampling

```go
var counter int64

func ProcessBid(bid Bid) error {
    // Only log 1% of bids
    if atomic.AddInt64(&counter, 1) % 100 == 0 {
        logger.Info("bid_processed", /* ... */)
    }
    // Always log errors
    if result.Error != nil {
        logger.Error("bid_failed", /* ... */)
    }
    return nil
}
```

**Pros:** Detailed logs for subset of requests
**Cons:** Might miss issues in unsampled requests

---

## The Real Solution: Combination

**Staff Engineer approach:**

1. **Production:** Sample + errors only (minimal overhead)
2. **Staging:** Full logging (for debugging)
3. **Dynamic sampling:** Increase sample rate when investigating issues

```go
// Log level can be changed at runtime
if logger.Level() >= zap.DebugLevel {
    // Full logging in debug mode
    logger.Debug("bid_debug", /* full details */)
} else {
    // Production: sampled
    if shouldLog() {
        logger.Info("bid_processed", /* summary */)
    }
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's buffered async logging? (Log to memory buffer, flush to disk asynchronously)
2. What's the trade-off with async logging? (Fast but can lose logs on crash)
3. What's log sampling? (Only log percentage of requests, like 1%)
4. What's the recommended production approach? (Sample + errors only in prod, full logging in staging)
5. Why log by severity level? (Always errors, sometimes warnings, rarely debug/info)

---

**Continue to `solution.md`**
