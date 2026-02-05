---
name: sec-101-secret-rotation
description: Secret Rotation Failure
difficulty: Intermediate
category: Security / Secrets / Rotation
level: Senior Engineer
---
# Security 101: Secret Rotation Failure

---

## Tools & Prerequisites

To debug and implement secret rotation:

### Secrets Management Tools

| Tool | Purpose | Quick Usage |
|------|---------|-------------|
| **AWS Secrets Manager** | Store & rotate secrets | `aws secretsmanager get-secret-value --secret-id db-cred` |
| **HashiCorp Vault** | Secrets management | `vault kv get secret/db-creds` |
| **Azure Key Vault** | Azure secrets | `az keyvault secret show --vault-name mykv --name db-pass` |
| **kubectl create secret** | Kubernetes secrets | `kubectl create secret generic db-pass --from-literal=password=xxx` |
| **envsubst** | Template-based config | `envsubst < config.template > config.env` |

### Key Commands

```bash
# AWS Secrets Manager - Rotate secret
aws secretsmanager rotate-secret --secret-id db-creds

# HashiCorp Vault - Dynamic database credentials
vault read database/creds/app-role

# Kubernetes - Check secret version
kubectl get secrets -o jsonpath='{.items[*].data.password}' | base64 -d

# Monitor connection pool errors
netstat -an | grep ESTABLISHED | grep :5432 | wc -l

# Check which processes have old credentials open
lsof | grep database | grep ESTABLISHED

# Test new credentials before rotation
PGPASSWORD=$NEW_PASS psql -h db-host -U app -c "SELECT 1"
```

### Key Concepts

**Secret Rotation**: Periodically changing credentials to limit exposure window.

**Connection Pooling**: Reusing database connections for performance; complicates rotation.

**Graceful Drain**: Process stops accepting new work while finishing existing requests.

**Zero-Downtime Rotation**: No service interruption during credential change.

**Blue-Green Deployment**: Maintain two environments with different secrets; switch traffic.

**Dual-Write Period**: Time when both old and new credentials are valid.

**Lease**: Time-limited secret access; auto-expires, forcing renewal.

**Dynamic Secrets**: On-demand credentials with short TTL (e.g., Vault database roles).

**Secret Versioning**: Tracking multiple versions of secrets for rollback capability.

---

## Visual: Secret Rotation

### Broken Rotation (Causes Downtime)

```mermaid
sequenceDiagram
    autonumber
    participant Admin
    participant DB as Database
    participant Config as Config File
    participant App as Application
    participant LB as Load Balancer

    Admin->>DB: ALTER USER password = 'new'
    Admin->>Config: Update password in file
    Admin->>App: Restart application

    Note over LB: Application restarts...

    App->>DB: Connect with new password
    DB-->>App: ✅ Connected

    LB->>App: Route traffic
    App->>DB: Query (cached connection)

    Note over App: Some instances have old<br/>cached connections!

    OtherApp->>DB: Connect with old password
    DB-->>OtherApp: ❌ Authentication failed!

    Note over LB: Connection refused errors!
```

### Zero-Downtime Rotation (Dual-Write)

```mermaid
sequenceDiagram
    autonumber
    participant Admin
    participant DB as Database
    participant Old as Old Creds
    participant New as New Creds
    participant App as Application

    Note over Admin,App: Phase 1: Add new credentials

    Admin->>DB: CREATE USER 'app_v2'@'%'
    Admin->>DB: GRANT permissions to 'app_v2'

    Note over Admin,App: Phase 2: Dual-write period

    par Update instances
        Admin->>App: Deploy with both credentials
        App->>DB: Try new, fallback to old
    and Test
        Admin->>DB: Verify app_v2 works
    end

    Note over Admin,App: Phase 3: Fully migrate

    Admin->>App: All instances use new
    Admin->>DB: DROP USER 'app'@'%'

    Note over Admin,App: Phase 4: Cleanup

    Admin->>App: Remove old credential config
```

### Connection Pool Refresh Strategy

```mermaid
flowchart TB
    subgraph Problem ["❌ Direct Password Change"]
        P1["DB password changed"]
        P2["Connection pool still has<br/>connections with old password"]
        P3["Next request: use pooled connection"]
        P4["❌ Auth error"]

        P1 --> P2 --> P3 --> P4
    end

    subgraph Solution ["✅ Graceful Pool Refresh"]
        S1["Signal app: refresh coming"]
        S2["App: drain connection pool"]
        S3["App: close all existing connections"]
        S4["DB: change password"]
        S5["App: create pool with new password"]

        S1 --> S2 --> S3 --> S4 --> S5
    end

    style Problem fill:#ffcdd2
    style Solution fill:#c8e6c9
```

### Dynamic Secrets vs Static Secrets

```mermaid
flowchart TB
    subgraph Static ["Static Secrets (Manual Rotation)"]
        ST1["Password stored in config"]
        ST2["Rotated quarterly (manual)"]
        ST3["If leaked: valid until next rotation"]
        ST4["Same password used by all instances"]

        ST1 --> ST2 --> ST3 --> ST4
    end

    subgraph Dynamic ["Dynamic Secrets (Auto Rotation)"]
        DY1["Credentials from Vault/Secrets Manager"]
        DY2["Short TTL (hours)"]
        DY3["Auto-rotate before expiry"]
        DY4["Unique per app instance"]

        DY1 --> DY2 --> DY3 --> DY4
    end

    style Static fill:#ffcdd2
    style Dynamic fill:#c8e6c9
```

### Blue-Green Rotation

```mermaid
sequenceDiagram
    autonumber
    participant LB as Load Balancer
    participant Blue as Blue (old creds)
    participant Green as Green (new creds)
    participant DB as Database

    Note over LB,DB: Initial: 100% traffic to Blue

    LB->>Blue: All traffic
    Blue->>DB: Queries with old creds

    Note over LB,DB: Rotation starts

    LB->>Green: Deploy with new creds
    Green->>DB: Test new creds work

    LB->>LB: Shift 10% traffic to Green
    LB->>LB: Shift 50% traffic to Green
    LB->>LB: Shift 100% traffic to Green

    Note over LB,DB: Green handles all traffic

    LB->>Blue: Deprovision blue
    DB->>DB: Remove old credentials
```

### Secrets Manager Integration

```mermaid
flowchart LR
    subgraph App ["Application"]
        Worker["Worker Process"]
    end

    subgraph SM ["Secrets Manager"]
        KV["Key-Value Store<br/>db-password: v1, v2, v3"]
        API["Secret API"]
    end

    subgraph DB ["Database"]

    end

    Worker -->|"GET /secret/db-password"| API
    API -->|"v3 (latest)"| Worker
    Worker -->|"Connect with v3"| DB

    SM -.->|"Auto-rotate"| SM
    Note1["Secret rotates every 24h<br/>Workers auto-fetch new version"]
```

### Rotation Failures

```mermaid
pie showData
    title "Secret Rotation Failure Causes"
    "Connection pool not drained" : 35
    "Config not reloaded" : 25
    "Partial deployment" : 20
    "Wrong secret in env" : 10
    "Race condition" : 10
```

### Lease-Based Credentials

```mermaid
sequenceDiagram
    autonumber
    participant App as Application
    participant Vault as Secrets Manager
    participant DB as Database

    Note over App,DB: Short-lived credentials (1 hour lease)

    App->>Vault: Request credentials
    Vault->>DB: Create temporary user with 1h expiry
    DB-->>Vault: temp_user_xyz, password_123
    Vault-->>App: Credentials (lease until 15:00)

    App->>DB: Connect as temp_user_xyz
    DB-->>App: Connected

    Note over App: After 1 hour...

    App->>DB: Query
    DB-->>App: ❌ User expired

    App->>Vault: Request new credentials
    Note over App: Automatic rotation!
```

---

## The Situation

You rotate database credentials quarterly. After rotation, production goes down.

**Your rotation process:**

```bash
# 1. Generate new password
NEW_PASS=$(openssl rand -base64 32)

# 2. Update database
mysql -e "ALTER USER 'app'@'%' IDENTIFIED BY '$NEW_PASS'"

# 3. Update config file
sed -i "s/DB_PASSWORD=.*/DB_PASSWORD=$NEW_PASS/" .env

# 4. Restart application
systemctl restart app
```

---

## The Incident

```
14:00 UTC - Start credential rotation
14:05 UTC - Database password updated
14:06 UTC - Config file updated
14:07 UTC - Application restart

14:08 UTC - "Connection refused" errors flood logs
14:10 UTC - Rollback to old password
14:15 UTC - Service recovers

Root cause: Load balancer had cached connections with old password
          New instances couldn't connect
          Old instances still worked until connections drained
```

---

## The Jargon

| Term | Definition |
|------|------------|
| **Secret Rotation** | Periodically changing credentials to limit exposure |
| **Connection Pooling** | Reusing database connections; caches credentials |
| **Graceful Drain** | Stop accepting new work while finishing existing requests |
| **Zero-Downtime** | No service interruption during change |
| **Blue-Green** | Two environments, switch traffic between them |
| **Dual-Write Period** | Time when both old and new credentials are valid |
| **Dynamic Secrets** | On-demand credentials with short TTL |
| **Lease** | Time-limited secret access; auto-expires |
| **Secret Versioning** | Tracking multiple versions for rollback |

---

## Questions

1. **Why did rotation cause downtime?** (Connection pool cache)

2. **How do you rotate secrets without downtime?** (Dual-write, drain pools)

3. **What's the difference between password rotation and key rotation?** (Keys can be versioned, passwords typically not)

4. **How should applications handle credential updates?** (Watch for changes, fetch from manager)

5. **As a Senior Engineer, what's your rotation strategy?**

---

**Read `step-01.md`**
