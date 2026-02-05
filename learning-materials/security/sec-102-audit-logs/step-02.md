# Step 2: Tamper-Evident Logging

---

## Write-Once Storage

**Options:**
- S3 with Object Lock (WORM)
- Cloudflare Workers KV (single-direction)
- Blockchain-based logging
- Append-only database tables
- Syslog to remote server (immediate send)

---

## Implementation Pattern

```go
package main

import (
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "fmt"
    "time"
)

type AuditLogger struct {
    sync.Mutex
    buffer chan *AuditEvent
    client *S3Client
    lastHash string
}

type AuditEvent struct {
    Timestamp string                 `json:"timestamp"`
    EventID   string                 `json:"event_id"`
    EventType string                 `json:"event_type"`
    Actor     Actor                  `json:"actor"`
    Target    *Target                `json:"target,omitempty"`
    Result    string                 `json:"result"`
    Metadata  map[string]interface{} `json:"metadata,omitempty"`
    Hash      string                 `json:"hash"`          // Current event hash
    PrevHash  string                 `json:"prev_hash"`     // Previous event hash
}

func (l *AuditLogger) Log(eventType string, actor Actor, target *Target, result string, metadata map[string]interface{}) error {
    event := &AuditEvent{
        Timestamp: time.Now().UTC().Format(time.RFC3339),
        EventID:   generateEventID(),
        EventType: eventType,
        Actor:     actor,
        Target:    target,
        Result:    result,
        Metadata:  metadata,
        PrevHash:  l.lastHash,
    }

    // Serialize event for hashing
    data, err := json.Marshal(event)
    if err != nil {
        return err
    }

    // Add cryptographic hash for tamper detection
    hash := sha256.Sum256(data)
    event.Hash = hex.EncodeToString(hash[:])

    // Update chain
    l.lastHash = event.Hash

    // Send immediately (don't buffer)
    return l.client.PutObject("audit-logs", event.EventID, event)
}

// Chain verification: each event hashes previous
func VerifyChain(events []*AuditEvent) bool {
    for i := 1; i < len(events); i++ {
        if events[i].PrevHash != events[i-1].Hash {
            return false  // Chain broken!
        }
    }
    return true
}
```

---

## S3 Object Lock Example

```go
package main

import (
    "context"
    "time"

    "github.com/aws/aws-sdk-go-v2/service/s3"
    "github.com/aws/aws-sdk-go-v2/service/s3/types"
)

type S3AuditLogger struct {
    client *s3.Client
    bucket string
}

func (l *S3AuditLogger) WriteLog(ctx context.Context, key string, data []byte) error {
    // Enable Object Lock (WORM - Write Once Read Many)
    putInput := &s3.PutObjectInput{
        Bucket:               &l.bucket,
        Key:                  &key,
        Body:                 bytes.NewReader(data),
        ObjectLockMode:       types.ObjectLockModeGovernance,
        ObjectLockRetainUntilDate: &types.Time{
            Time: time.Now().Add(365 * 24 * time.Hour), // 1 year
        },
        ObjectLockLegalHold:  types.ObjectLockLegalHoldOn,
    }

    _, err := l.client.PutObject(ctx, putInput)
    return err
}

func (l *S3AuditLogger) VerifyLog(ctx context.Context, key string) (bool, error) {
    // Try to delete - should fail with legal hold
    _, err := l.client.DeleteObject(ctx, &s3.DeleteObjectInput{
        Bucket: &l.bucket,
        Key:    &key,
    })

    // If delete succeeded, log wasn't properly protected!
    if err == nil {
        return false, fmt.Errorf("log was deletable - not protected!")
    }

    return true, nil
}
```

---

## Immutable Table Pattern (PostgreSQL)

```sql
-- Create append-only audit table
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    result TEXT NOT NULL,
    metadata JSONB,
    hash TEXT NOT NULL,
    prev_hash TEXT NOT NULL,

    -- Prevent updates and deletes
    CONSTRAINT no_update CHECK (false)  -- Always false, prevents UPDATE
);

-- Prevent updates at table level
CREATE TRIGGER prevent_audit_update
    BEFORE UPDATE ON audit_logs
    EXECUTE FUNCTION raise_exception();

-- Prevent deletes at table level
CREATE TRIGGER prevent_audit_delete
    BEFORE DELETE ON audit_logs
    EXECUTE FUNCTION raise_exception();

CREATE OR REPLACE FUNCTION raise_exception()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Audit logs are immutable';
END;
$$ LANGUAGE plpgsql;

-- Create index for querying
CREATE INDEX idx_audit_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX idx_audit_actor ON audit_logs(actor_id);
CREATE INDEX idx_audit_type ON audit_logs(event_type);
```

---

## Real-Time Streaming

```go
package main

import (
    "context"
    "encoding/json"

    "github.com/segmentio/kafka-go"
)

type KafkaAuditLogger struct {
    writer *kafka.Writer
}

func NewKafkaAuditLogger(brokers []string, topic string) *KafkaAuditLogger {
    return &KafkaAuditLogger{
        writer: &kafka.Writer{
            Addr:     kafka.TCP(brokers...),
            Topic:    topic,
            Balancer: &kafka.LeastBytes{},
            // Async writes for performance
            Async:    true,
            // Required Acks for durability
            RequiredAcks: kafka.RequireAll,
        },
    }
}

func (l *KafkaAuditLogger) Log(ctx context.Context, event AuditEvent) error {
    // Serialize event
    data, err := json.Marshal(event)
    if err != nil {
        return err
    }

    // Send to Kafka (distributed, replicated log)
    return l.writer.WriteMessages(ctx, kafka.Message{
        Key:   []byte(event.EventID),  // Partition by event_id
        Value: data,
        // Add headers for metadata
        Headers: []kafka.Header{
            {Key: "event_type", Value: []byte(event.EventType)},
            {Key: "actor_id", Value: []byte(event.Actor.UserID)},
            {Key: "timestamp", Value: []byte(event.Timestamp)},
        },
    })
}

func (l *KafkaAuditLogger) Close() error {
    return l.writer.Close()
}
```

---

## Verification Script

```bash
#!/bin/bash
# verify-audit-chain.sh

# Fetch all audit logs from S3
aws s3 ls s3://audit-logs/ --recursive | while read -r line; do
    key=$(echo "$line" | awk '{print $4}')
    aws s3 cp "s3://audit-logs/$key" - | jq -c '.'
done > /tmp/all_logs.json

# Verify chain integrity
go run verify.go -logs /tmp/all_logs.json

# Output:
# ✓ Chain verified: 10,000 events
# ✓ First event: evt_001 (2024-01-01T00:00:00Z)
# ✓ Last event: evt_10000 (2024-12-31T23:59:59Z)
# ✓ No gaps detected
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's WORM storage? (Write Once Read Many - prevents modification/deletion after write)
2. How does hash chaining work? (Each event contains hash of previous event; broken chain indicates tampering)
3. What's S3 Object Lock? (WORM mode that prevents deletion/modification for specified duration)
4. Why stream audit logs to Kafka? (Distributed, durable log; real-time processing; prevents local tampering)
5. What's the immutable table pattern? (Database table with triggers preventing UPDATE/DELETE operations)

---

**Read `solution.md`**
