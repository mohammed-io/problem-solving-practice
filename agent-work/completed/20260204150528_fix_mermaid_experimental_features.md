# Fix Mermaid Experimental Features

## Status: completed (20260204154926)

## Context
The problem-solving-coach markdown files contain experimental Mermaid features like `xychart-beta` and `pie title` that may not be supported in all Mermaid renderers. These need to be replaced with standard markdown tables or text lists for better compatibility.

## Value Proposition
- Replace xychart-beta with markdown tables
- Replace pie charts with markdown tables or text lists
- Fix multi-line text in Mermaid nodes with <br/> tags
- Ensure all diagrams render consistently across different Mermaid versions

## Alternatives considered
- Keep experimental features: Poor compatibility
- Use images: Harder to maintain, not text-based
- Markdown tables: Best option for compatibility and maintainability

## Todos
- [x] Fix /Users/mohammed/Projects/resume/problem-solving-coach/observability/obs-101-cardinality-explosion/problem.md
- [x] Fix /Users/mohammed/Projects/resume/problem-solving-coach/performance/perf-104-numa-effects/problem.md
- [x] Fix /Users/mohammed/Projects/resume/problem-solving-coach/performance/perf-101-memory-fragmentation/problem.md
- [x] Fix /Users/mohammed/Projects/resume/problem-solving-coach/network/net-104-lb-oscillation/problem.md
- [x] Fix /Users/mohammed/Projects/resume/problem-solving-coach/intermediate/incident-015-cache-avalanche/problem.md
- [x] Fix /Users/mohammed/Projects/resume/problem-solving-coach/basic/incident-003-cache-stampede/problem.md
- [x] Fix /Users/mohammed/Projects/resume/problem-solving-coach/performance/perf-102-gc-pauses/problem.md
- [x] Fix /Users/mohammed/Projects/resume/problem-solving-coach/advanced/design-100-consistent-hash/problem.md
- [x] Fix /Users/mohammed/Projects/resume/problem-solving-coach/advanced/postgres-104-cursor-pagination/problem.md
- [x] Fix /Users/mohammed/Projects/resume/problem-solving-coach/advanced/postgres-100-mvcc-revealed/problem.md
- [x] Fix /Users/mohammed/Projects/resume/problem-solving-coach/advanced/incident-106-backpressure/problem.md
- [x] Fix /Users/mohammed/Projects/resume/problem-solving-coach/intermediate/incident-012-hot-partition/problem.md
- [x] Fix /Users/mohammed/Projects/resume/problem-solving-coach/intermediate/incident-011-replica-lag/problem.md
- [x] Fix /Users/mohammed/Projects/resume/problem-solving-coach/advanced/design-103-eventual-consistency/step-01.md
- [x] Fix /Users/mohammed/Projects/resume/problem-solving-coach/intermediate/incident-010-split-brain/problem.md
- [x] Fix /Users/mohammed/Projects/resume/problem-solving-coach/network/net-101-dns-ttl/problem.md
- [x] Fix /Users/mohammed/Projects/resume/problem-solving-coach/network/net-102-tcp-timewait/problem.md
- [x] Fix /Users/mohammed/Projects/resume/problem-solving-coach/security/sec-103-rate-limit-bypass/problem.md
- [x] Fix /Users/mohammed/Projects/resume/problem-solving-coach/observability/obs-103-slo-calculation/problem.md

## Notes
