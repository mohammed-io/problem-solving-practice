---
name: sec-102-audit-logs
description: Audit Log Gaps
difficulty: Intermediate
category: Security / Audit / Compliance
level: Senior Engineer
---
# Security 102: Audit Log Gaps

---

## The Situation

You're building a financial app. Regulations require audit logs for all sensitive actions.

**Your logging:**
```go
func (s *Service) TransferMoney(from, to string, amount float64) error {
    log.Info("Transfer initiated", "from", from, "to", to, "amount", amount)

    if err := s.db.Transfer(from, to, amount); err != nil {
        log.Error("Transfer failed", "error", err)
        return err
    }

    log.Info("Transfer completed")
    return nil
}
```

---

## The Incident

```
Security audit reveals gaps:

1. Admin actions not logged
   - "Who deleted user X?" → No record

2. Bulk operations missing context
   - CSV import of 1000 users → Single log entry
   - Can't tell which user was added by whom

3. Log tampering possible
   - Logs stored locally on same server
   - Admin with SSH access could modify logs

4. Sensitive data in logs
   - Passwords, tokens logged accidentally
   - GDPR violation

5. Logs lost during restart
   - No log aggregation
   - In-memory logs lost on crash
```

---

## Questions

1. **What should be logged?**

2. **How do you prevent log tampering?**

3. **Where should logs be stored?**

4. **How to handle sensitive data in logs?**

5. **As a Senior Engineer, what's your audit logging strategy?**

---

## Jargon

| Term | Definition |
|------|------------|
| **Audit Log** | Immutable record of security-relevant events |
| **Tamper-Evident** | Detects if logs were modified |
| **Write-Once** | Cannot be modified after writing |
| **SIEM** | Security Information and Event Management |
| **Immutability** | Cannot be changed |
| **Chain of Custody** | Documented handling of evidence |

---

**Read `step-01.md`**
