# Problem-Solving Coach

**A system of 26 realistic engineering problems to build your troubleshooting intuition and system design skills.**

---

## What This Is

This is a structured learning system designed to develop **engineering intuition** through realistic scenarios. Each problem is based on real incidents that happened at companies, anonymized but technically accurate.

### What You'll Learn

| Category | Problems | Skills Built |
|----------|----------|--------------|
| **Incidents** | 14 | Systematic troubleshooting, incident response, root cause analysis |
| **Database Design** | 6 | Schema design, indexing strategies, query optimization, trade-offs |
| **PostgreSQL Internals** | 4 | How Postgres really works, MVCC, vacuum, WAL, query planning |
| **System Design** | 2 | Architectural patterns, scalability, reliability |

### Difficulty Levels

| Level | Problems | Focus |
|-------|----------|-------|
| **Basic** | 10 | Single service, clear symptoms, standard patterns |
| **Intermediate** | 10 | Multiple services, correlation needed, non-obvious causes |
| **Advanced** | 6 | Distributed systems, subtle issues, multiple valid approaches |

---

## How To Use

### The Coaching Process

Each problem has progressive steps. **Read only one step at a time.**

```
1. Read problem.md
2. Think about it
3. When stuck, read step-01.md
4. Think more
5. When stuck again, read step-02.md
6. Continue until you solve it or reach solution.md
```

### Rules

1. **Don't skip steps** - Each step narrows the problem slightly
2. **Take your time** - Real problems aren't solved in 30 seconds
3. **Write down your thinking** - Builds metacognition
4. **Check solution.md last** - Contains full analysis with trade-offs
5. **Revisit problems** - Coming back later tests retention

---

## Directory Structure

```
problem-solving-coach/
├── README.md              # This file
├── guide.md               # Coaching philosophy & methodology
├── terminology.md         # Jargon dictionary (lookup unfamiliar terms)
│
├── basic/                 # 10 fundamental problems
│   ├── incident-001-slow-api/
│   ├── incident-002-db-connection-pool/
│   ├── incident-003-cache-stampede/
│   ├── incident-004-memory-leak/
│   ├── incident-005-n+1-query/
│   ├── design-001-user-schema/
│   ├── design-002-message-queue/
│   ├── design-003-rate-limiter/
│   ├── postgres-001-index-usage/
│   └── postgres-002-vacuum-bloat/
│
├── intermediate/          # 10 multi-service problems
│   ├── incident-010-split-brain/
│   ├── incident-011-replica-lag/
│   ├── incident-012-hot-partition/
│   ├── incident-013-deadlock/
│   ├── incident-014-sli-breach/
│   ├── incident-015-cache-avalanche/
│   ├── incident-016-slow-log/
│   ├── design-010-sharded-key-value/
│   ├── design-011-event-sourcing/
│   └── postgres-010-cte-vs-subquery/
│
└── advanced/              # 6 distributed system problems
    ├── incident-100-distributed-deadlock/
    ├── incident-101-cascade-failure/
    ├── incident-102-thundering-herd/
    ├── incident-103-phoenix-deadlock/
    ├── design-100-consistent-hash/
    └── postgres-100-mvcc-revealed/
```

---

## Problem Format

Each problem contains:

```
problem-name/
├── problem.md          # The scenario, context, symptoms
├── step-01.md          # First coaching hint (broad guidance)
├── step-02.md          # Second hint (more specific)
├── ...                 # Additional steps as needed
└── solution.md         # Full analysis + trade-offs + what really happened
```

---

## Incident Response Coaching

Some problems include **operational coaching** - teaching you when and how to communicate during real incidents.

### When to Page

| Severity | Action | Example |
|----------|--------|---------|
| P0 - Critical | Page immediately | Service down, data loss |
| P1 - High | Page within 15 min | Degraded performance, SLO at risk |
| P2 - Medium | Slack/ticket | Elevated errors, partial outage |
| P3 - Low | Backlog | Minor issues, no user impact |

### Incident Report Format

When you identify an incident, your report should include:

```markdown
## Incident Report

**Severity:** P0/P1/P2/P3
**Time Started:** YYYY-MM-DD HH:MM UTC
**Service:** Affected service(s)

### Symptoms
What are you seeing?

### Impact
Who is affected? How many users?

### Current Status
What are you doing?

### Next Steps
What will you do next?
```

---

## Real Incident Sources

Problems are based on incidents from:

- **Cloudflare** - DNS outage, route leakage
- **AWS** - US-EAST-1 outage, S3 availability
- **GitHub** - Database connection pool exhaustion
- **Stripe** - API latency spikes
- **Uber** - PostgreSQL bloat issues
- **Cockroach Labs** - Range tombstone issues
- **Google** - GCP outage
- **Facebook/Meta** - BGP config error
- **Slack** - Message delivery delays
- **Shopify** - Black Friday scaling challenges
- **Cloudflare** - Cloudflare's outage (CPU exhaustion)
- **GitLab** - Database deletion incident
- **Basecamp** - 17-hour outage

*(Technical details preserved, company attribution included for learning)*

---

## Terminology

**Jargon is used deliberately.** When you encounter unfamiliar terms:

1. Try to understand from context
2. Check `terminology.md` for definition
3. Look it up externally if needed

This builds your technical vocabulary - critical for senior roles.

---

## Progression Path

### Start Here (If New)
1. `basic/incident-001-slow-api.md` - Introduction to RED method
2. `basic/design-001-user-schema.md` - Introduction to database trade-offs
3. `basic/postgres-001-index-usage.md` - Introduction to query planning

### Then Continue
4. Complete all basic problems (can do in any order)
5. Move to intermediate problems
6. Finish with advanced problems

### Revisit Periodically
- Problems you solved quickly - revisit in 2 weeks
- Problems that stumped you - revisit in 1 month
- Advanced problems - worth revisiting quarterly

---

## What Makes This Different

| Traditional Learning | Problem-Solving Coach |
|---------------------|----------------------|
| Single solution | Trade-offs discussed |
| Clean examples | Real-world messiness |
| Right/wrong answers | "It depends" thinking |
| Theoretical problems | Actual incidents |
| Immediate answers | Progressive hints |

---

## Contributing

This is a personal learning system. As you solve problems, note:
- Which steps were most helpful?
- What confused you?
- What would you add?

Consider writing your own problems based on incidents you encounter!

---

**Start with `basic/incident-001-slow-api/` when ready.**
