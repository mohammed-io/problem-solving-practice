# BGP Route Leak Lab

Demonstrates BGP route leaks and prefix hijacking using FRR (Free Range Routing).

## Quick Start

```bash
./start.sh
```

## What This Lab Demonstrates

1. **Normal BGP Operation**: How legitimate route announcements work
2. **Route Leak Detection**: Identifying duplicate route announcements
3. **AS Path Analysis**: Tracing route paths to detect anomalies
4. **Prefix Length**: How more specific prefixes win routing decisions
5. **RPKI Validation**: How cryptographic route validation prevents leaks
6. **Mitigation Strategies**: Best practices for BGP security

## The Cloudflare Incident (2018)

A small Virginia ISP accidentally announced BGP routes for Cloudflare's IP prefixes.
This caused significant portions of Cloudflare's traffic to be routed through the ISP,
overwhelming their capacity and causing outages.

**Root Cause**: The ISP wasn't filtering customer announcements properly.

## Cleanup

```bash
docker-compose down
```

## Experiments

### 1. Normal Operation
See how BGP routes are normally announced and propagated.

### 2. Route Leak
Simulate a route leak where an ISP announces prefixes they don't own.

### 3. AS Path Analysis
Analyze AS paths to detect routing anomalies.

### 4. Prefix Length
Understand how more specific prefixes are preferred over broader ones.

### 5. RPKI
Learn about Route Origin Authorization and how it prevents leaks.

### 6. Mitigation
Explore strategies to prevent and detect route leaks.
