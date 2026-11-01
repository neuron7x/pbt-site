# Synthetic runtime soak — predeclared verification contract

- PR CI executes a **real elapsed 1800-second minimum** fault-injection soak in an isolated GitHub runner; `smoke` exercises the same harness for 10 seconds in the regular test suite.
- Test inputs are synthetic; CRM is a local HMAC-checking fault-injection server. The test does not contact production systems, use actual client data, or assert production/field performance.
- Fixed policies live in `config/runtime-soak-budgets.json` with anti-weakening tests. Changing budgets needs a separate evidence-based engineering justification, not a CI shortcut.
- Every accepted HTTP 201 must correspond to precisely one committed lead and a delivered outbox row by the end, permitting **at-least-once webhook retries**.
- Injected status responses: 408/429/503; an intentional downstream timeout; SIGKILL and restart with the original SQLite DB; idempotent request replays; two SQLite online backup checkpoints; HMAC verification of every received webhook.
- Metrics: observed elapsed seconds, accepted count, API p50/p95/p99, maximum RSS and in-process RSS growth sampled from Linux `/proc`, thread bound, backlog peak, final delivery attempts, backup integrity, restart and checksum-pinned GitHub artifact.
- A green synthetic soak is **not** real-user INP, live CRM acceptance, unlimited reliability, or 24/7 production certification. A future production SLO and RPO still require the owner's published policy.

An independent verifier (`tools/verify_soak_evidence.py`) checks immutable
source SHA, raw latency samples and their p99, per-process RSS time-series,
injected HTTP fault-class coverage, all storage/HMAC counters, and the predeclared
limits. A fabricated `status: PASS` field without matching raw evidence is
rejected. This still does not constitute external production certification.

## Exact-main execution and truthful provenance (2026-11-01)

The Actions workflow accepts protected `push` on `main` for runtime-relevant
paths, an explicitly initiated `workflow_dispatch` on `main`, and PRs
against `main`. All modes pin checkout to the event's immutable commit SHA,
then compare the measured report's `source_sha` to the same `PBT_HEAD_SHA`.
PR runs pin the PR source head, not the synthetic merge ref. A PR run on a
workflow-only change is **not** evidence for the exact commit on `main`;
it can demonstrate that application code matches by an independent tree diff,
but the complete exact-main gate requires its own event/receipt.

On CI, `tools/perf_probe.py` records actual checked-out `execution_sha`,
the expected `branch_head_sha`, and `event_sha` separately. A mismatched
checked-out revision fails instead of silently recording a PR synthetic merge
SHA as the execution revision. The 1800-second soak is synthetic, not a live
CRM receipt, production resilience proof, or field CWV/INP measurement.
