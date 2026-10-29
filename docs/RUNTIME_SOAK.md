# Synthetic runtime soak — predeclared verification contract

- PR CI executes a **real elapsed 1800-second minimum** fault-injection soak in an isolated GitHub runner; `smoke` exercises the same harness for 10 seconds in the regular test suite.
- Test inputs are synthetic; CRM is a local HMAC-checking fault-injection server. The test does not contact production systems, use actual client data, or assert production/field performance.
- Fixed policies live in `config/runtime-soak-budgets.json` with anti-weakening tests. Changing budgets needs a separate evidence-based engineering justification, not a CI shortcut.
- Every accepted HTTP 201 must correspond to precisely one committed lead and a delivered outbox row by the end, permitting **at-least-once webhook retries**.
- Injected status responses: 408/429/503; an intentional downstream timeout; SIGKILL and restart with the original SQLite DB; idempotent request replays; two SQLite online backup checkpoints; HMAC verification of every received webhook.
- Metrics: observed elapsed seconds, accepted count, API p50/p95/p99, maximum RSS and in-process RSS growth sampled from Linux `/proc`, thread bound, backlog peak, final delivery attempts, backup integrity, restart and checksum-pinned GitHub artifact.
- A green synthetic soak is **not** real-user INP, live CRM acceptance, unlimited reliability, or 24/7 production certification. A future production SLO and RPO still require the owner's published policy.
