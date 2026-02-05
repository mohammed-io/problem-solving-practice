# Restructure All Learning Problems

## Status: in_progress

## Context
Currently, most learning problems only have 2 steps (step-01.md and step-02.md). For effective coaching, learners need more granular, progressive steps that build understanding gradually. Only 4 problems have been restructured so far with multi-step learning paths.

## Value Proposition
- Each problem will have as many steps as needed for effective coaching
- Steps should guide learners progressively toward the solution
- Each step ends with a "Quick Check" to validate understanding
- All code examples in Go (not Python)

## Alternatives considered
- Keep all problems at 2 steps: Too shallow for complex topics
- Add steps only to design problems: Incident/observability problems also need depth
- Dynamic step generation: Manual curation ensures better learning paths

## Todos
- [x] Audit all problems and categorize by complexity
- [x] Restructure advanced design problems (consistent-hash, idempotency, CAP, eventual-consistency)
- [ ] Restructure advanced incident problems (distributed-deadlock, cascade-failure, thundering-herd, phoenix-deadlock, two-phase-commit, leader-election, backpressure, quorum-drift, lease-expiration)
- [ ] Restructure advanced postgres problems (mvcc-revealed, schema-migration, cursor-pagination, write-skew, foreign-key-cascade, generated-columns)
- [ ] Restructure basic design problems (user-schema, message-queue, rate-limiter)
- [ ] Restructure basic incident problems (slow-api already done, db-pool, cache-stampede, memory-leak, n-plus-one-products)
- [x] Restructure basic postgres problems (index-usage, vacuum-bloat)
- [x] Restructure intermediate design problems (sharded-kv, event-sourcing)
- [x] Restructure intermediate incident problems (split-brain, replica-lag, hot-partition, deadlock, sli-breach, cache-avalanche, slow-log)
- [x] Restructure intermediate postgres problems (cte-vs-subquery)
- [ ] Restructure network problems (dns-ttl, tcp-timewait, tls-handshake, lb-oscillation)
- [ ] Restructure observability problems (cardinality-explosion, tracing-gaps, slo-calculation, alert-fatigue)
- [ ] Restructure performance problems (memory-fragmentation, gc-pauses, cpu-throttling, numa-effects)
- [ ] Restructure real-world incidents (github-mysql, cloudflare-bgp, stackoverflow-ipv6, gitlab-rm-rf, facebook-bgp, aws-cassandra-outage)
- [ ] Restructure security problems (secret-rotation, audit-logs, rate-limit-bypass, token-revocation)
- [ ] Update all problem.md files with new learning paths

## Notes
- Use Go for all code examples
- Add "Quick Check" section at end of each step
- Each step should build on the previous one
- Not every problem needs more than 2 steps - use judgment
