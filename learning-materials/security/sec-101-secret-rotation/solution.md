# Solution: Zero-Downtime Secret Rotation

---

## Root Cause

Connection pools cached connections with old password. New instances failed to connect.

---

## Solution

**Two-phase rotation:**

```bash
#!/bin/bash
# rotate_password.sh

NEW_PASS=$(openssl rand -base64 32)

# Phase 1: Add new password, keep old
mysql -e "ALTER USER 'app'@'%' IDENTIFIED BY '$NEW_PASS' RETAIN CURRENT PASSWORD;"

# Phase 2: Rotate all applications
# Blue-green deploy or rolling restart
for instance in $(kubectl get pods -l app=api -o name); do
    # Update secret
    kubectl create secret generic db-creds --from-literal=password=$NEW_PASS --dry-run=client -o yaml | kubectl apply -f -

    # Restart pod (gracefully, with drain)
    kubectl delete $instance
    sleep 30  # Wait for new pod to be ready
done

# Phase 3: Remove old password
mysql -e "ALTER USER 'app'@'%' DISCARD OLD PASSWORD;"
```

**Better: Use Vault with leases:**

```
Vault secrets have TTL (time-to-live)
Applications request credentials with renew
Vault rotates credentials automatically
Applications fetch new credentials on renewal
```

---

## Quick Checklist

- [ ] Support dual credentials during rotation
- [ ] Rolling restart with health checks
- [ ] Connection pool drains before close
- [ ] Test rotation in staging first
- [ ] Automated rollback plan

---

**Next Problem:** `security/sec-102-audit-logs/`
