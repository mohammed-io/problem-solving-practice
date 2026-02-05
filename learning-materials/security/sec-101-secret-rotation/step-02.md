# Step 2: Zero-Downtime Rotation

---

## Database Supports Dual Password

```sql
-- MySQL 8.0+: RETAIN CURRENT PASSWORD
ALTER USER 'app'@'%'
  IDENTIFIED BY 'new_password'
  RETAIN CURRENT PASSWORD;

-- Now BOTH passwords work!
-- Old connections continue working
-- New connections use new password

-- After all apps rotated, remove old:
ALTER USER 'app'@'%'
  DISCARD OLD PASSWORD;
```

**PostgreSQL approach:**

```sql
-- PostgreSQL doesn't support dual password natively
-- Use two users with same grants during rotation:

-- Step 1: Create new user with new password
CREATE USER 'app_v2'@'%' IDENTIFIED BY 'new_password';
GRANT ALL PRIVILEGES ON app_db.* TO 'app_v2'@'%';

-- Step 2: Rotate apps to use app_v2 credentials

-- Step 3: Drop old user
DROP USER 'app'@'%';
```

---

## Application Pattern: Watch for Changes

```go
package main

import (
    "fmt"
    "os"
    "time"

    "github.com/fsnotify/fsnotify"
    _ "github.com/go-sql-driver/mysql"
)

type SecretWatcher struct {
    currentDBPassword string
    reloadChan        chan string
}

func (w *SecretWatcher) WatchDBPassword(path string) {
    watcher, err := fsnotify.NewWatcher()
    if err != nil {
        log.Fatal(err)
    }
    defer watcher.Close()

    err = watcher.Add(path)
    if err != nil {
        log.Fatal(err)
    }

    for {
        select {
        case event := <-watcher.Events:
            if event.Op&fsnotify.Write == fsnotify.Write {
                newPassword := w.readDBPassword(path)
                if newPassword != w.currentDBPassword {
                    w.currentDBPassword = newPassword
                    w.reloadChan <- newPassword
                }
            }
        case err := <-watcher.Errors:
            log.Println("Error:", err)
        }
    }
}

func (p *ConnectionPool) RotateConnection() {
    for newPassword := range p.reloadChan {
        // Close old connections gracefully
        p.drain()

        // New connections will use new password
        p.password = newPassword
        log.Printf("Rotated to new password")
    }
}

func (p *ConnectionPool) drain() {
    """Close all connections in the pool"""
    for _, conn := range p.connections {
        conn.Close()
    }
    p.connections = nil
}
```

---

## Full Rotation Script

```bash
#!/bin/bash
# zero_downtime_rotation.sh

DB_HOST="db.example.com"
DB_USER="app"
OLD_PASSWORD="old_password_123"
NEW_PASSWORD="new_password_456"
APPS=("app1" "app2" "app3")

echo "=== Zero-Downtime Password Rotation ==="

# Phase 1: Enable dual password on database
echo "Phase 1: Enabling dual password..."
mysql -h $DB_HOST -u admin -p <<EOF
ALTER USER '$DB_USER'@'%' IDENTIFIED BY '$NEW_PASSWORD' RETAIN CURRENT PASSWORD;
FLUSH PRIVILEGES;
EOF

# Verify both passwords work
echo "Verifying both passwords work..."
echo "SELECT 1" | mysql -h $DB_HOST -u $DB_USER -p$OLD_PASSWORD
echo "SELECT 1" | mysql -h $DB_HOST -u $DB_USER -p$NEW_PASSWORD

if [ $? -ne 0 ]; then
    echo "ERROR: Dual password verification failed!"
    exit 1
fi

# Phase 2: Rotate all applications
echo "Phase 2: Rotating applications..."
for app in "${APPS[@]}"; do
    echo "Rotating $app..."

    # Update secret store (Vault, AWS Secrets Manager, etc.)
    vault kv put secret/$app/db-password value="$NEW_PASSWORD"

    # Trigger config reload (signal, endpoint, etc.)
    curl -X POST http://$app:8080/-/reload

    # Wait for app to be healthy
    ./wait-for-healthy.sh $app

    echo "$app rotated successfully"
done

# Phase 3: Remove old password from database
echo "Phase 3: Removing old password..."
mysql -h $DB_HOST -u admin -p <<EOF
ALTER USER '$DB_USER'@'%' DISCARD OLD PASSWORD;
FLUSH PRIVILEGES;
EOF

# Verify only new password works
echo "Verifying rotation complete..."
echo "SELECT 1" | mysql -h $DB_HOST -u $DB_USER -p$NEW_PASSWORD

if [ $? -eq 0 ]; then
    echo "=== Rotation successful ==="
else
    echo "ERROR: New password doesn't work!"
    exit 1
fi
```

---

## Alternative: Connection Pool with Refresh

```go
package main

import (
    "database/sql"
    "time"
    _ "github.com/lib/pq"
)

type RefreshingPool struct {
    db          *sql.DB
    dsn         string
    password    string
    lastRefresh time.Time
    refreshInterval time.Duration
}

func NewRefreshingPool(dsn, password string) *RefreshingPool {
    return &RefreshingPool{
        dsn:             dsn,
        password:        password,
        refreshInterval: 30 * time.Second,
    }
}

func (p *RefreshingPool) Get() (*sql.Conn, error) {
    // Check if we need to refresh password
    if time.Since(p.lastRefresh) > p.refreshInterval {
        newPassword := p.fetchPasswordFromSecretStore()
        if newPassword != p.password {
            p.password = newPassword
            p.reconnect()
        }
        p.lastRefresh = time.Now()
    }

    return p.db.Conn()
}

func (p *RefreshingPool) reconnect() error {
    // Close old connections
    if p.db != nil {
        p.db.Close()
    }

    // Create new connection with fresh password
    dsn := fmt.Sprintf("%s:password@%s", p.dsn, p.password)
    db, err := sql.Open("postgres", dsn)
    if err != nil {
        return err
    }

    p.db = db
    return nil
}

func (p *RefreshingPool) fetchPasswordFromSecretStore() string {
    // Fetch from Vault, AWS Secrets Manager, etc.
    resp, _ := http.Get("https://vault.example.com/v1/secret/db/password")
    // Parse and return password
    return newPassword
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's the MySQL dual password feature? (RETAIN CURRENT PASSWORD allows both old and new passwords to work simultaneously)
2. How do you rotate PostgreSQL without dual password? (Create second user with same grants, rotate to it, then drop old user)
3. What's the file watcher pattern? (Watch config file for changes, trigger connection pool drain when password changes)
4. What's the full rotation flow? (Enable dual password → Rotate all apps → Remove old password)
5. Why use a secret store? (Centralized password management, automatic refresh, audit trail)

---

**Read `solution.md`**
