# Step 1: What to Log

---

## Audit Event Categories

**Identity & Access:**
- Login attempts (success/failure)
- Password changes
- Permission grants/revokes
- MFA enabled/disabled

**Data Access:**
- Records viewed (especially sensitive data)
- Data exports
- Searches on PII

**Configuration Changes:**
- Settings modified
- Features enabled/disabled
- Integrations added/removed

**Admin Actions:**
- User creation/deletion
- Role changes
- System restarts
- Certificate rotations

---

## Log Format

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "event_id": "evt_abc123",
  "event_type": "user.login.success",
  "actor": {
    "user_id": "usr_123",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0..."
  },
  "target": {
    "type": "user",
    "id": "usr_456"
  },
  "result": "success",
  "metadata": {
    "mfa_used": true,
    "login_method": "sso"
  }
}
```

---

## Audit Logger Implementation

```go
package main

import (
    "encoding/json"
    "time"
)

type AuditEvent struct {
    Timestamp string                 `json:"timestamp"`
    EventID   string                 `json:"event_id"`
    EventType string                 `json:"event_type"`
    Actor     Actor                  `json:"actor"`
    Target    *Target                `json:"target,omitempty"`
    Result    string                 `json:"result"`
    Metadata  map[string]interface{} `json:"metadata,omitempty"`
}

type Actor struct {
    UserID    string `json:"user_id"`
    IPAddress string `json:"ip_address"`
    UserAgent string `json:"user_agent"`
}

type Target struct {
    Type string `json:"type"`
    ID   string `json:"id"`
}

type AuditLogger struct {
    backend LogBackend
}

func NewAuditLogger(backend LogBackend) *AuditLogger {
    return &AuditLogger{backend: backend}
}

func (l *AuditLogger) Log(eventType string, actor Actor, target *Target, result string, metadata map[string]interface{}) error {
    event := AuditEvent{
        Timestamp: time.Now().UTC().Format(time.RFC3339),
        EventID:   generateEventID(),
        EventType: eventType,
        Actor:     actor,
        Target:    target,
        Result:    result,
        Metadata:  metadata,
    }

    data, err := json.Marshal(event)
    if err != nil {
        return err
    }

    return l.backend.Write(data)
}

func (l *AuditLogger) LogLogin(actor Actor, success bool, mfaUsed bool) error {
    metadata := map[string]interface{}{
        "mfa_used": mfaUsed,
    }

    result := "success"
    eventType := "user.login.success"
    if !success {
        result = "failure"
        eventType = "user.login.failure"
    }

    return l.Log(eventType, actor, nil, result, metadata)
}

func (l *AuditLogger) LogDataAccess(actor Actor, recordType, recordID string) error {
    metadata := map[string]interface{}{
        "record_type": recordType,
        "record_id":   recordID,
    }

    target := &Target{Type: recordType, ID: recordID}
    return l.Log("data.access", actor, target, "success", metadata)
}

func generateEventID() string {
    return fmt.Sprintf("evt_%s", randomID())
}
```

---

## Structured Logging Best Practices

**DO:**
```go
// Good: Structured, queryable
logger.Log("user.login.success", map[string]interface{}{
    "user_id": "usr_123",
    "ip": "192.168.1.1",
    "mfa": true,
})
```

**DON'T:**
```go
// Bad: Unstructured, hard to query
logger.Info("User usr_123 logged in from 192.168.1.1 with MFA")
```

---

## Quick Check

Before moving on, make sure you understand:

1. What are the main audit event categories? (Identity & Access, Data Access, Configuration Changes, Admin Actions)
2. What's a structured log format? (JSON with consistent field names: timestamp, event_id, event_type, actor, target, result, metadata)
3. Why include actor information? (Know WHO did WHAT - user ID, IP address for attribution)
4. What's the difference between event_type and result? (event_type is what happened, result is success/failure)
5. Why log data access events? (Track who viewed sensitive data for compliance and forensics)

---

**Read `step-02.md`**
