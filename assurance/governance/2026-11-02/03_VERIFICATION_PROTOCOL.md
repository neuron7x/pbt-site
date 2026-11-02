# PBT · Execution, Falsification and Evidence Protocol

**Authority:** [AGENTS.md](../../../AGENTS.md), sealed [48 tasks](../../../assurance/source/tasks.json), [ledger](../../../assurance/ledger.json), [case](../../../assurance/case.json), [controller #15](https://github.com/neuron7x/pbt-site/issues/15), [risk #6](https://github.com/neuron7x/pbt-site/issues/6). Language of operational IDs/prompts: English; human documentation: Ukrainian.

## 1. Dispatch and file ownership

1. GET authenticated `main` SHA and tree, all open/last PRs, branches, new commits, review threads, owner handoff markers and exact-head jobs before starting. Do not reuse historical SHA.
2. Treat local Claude Opus, unpushed edits and subscription state as **UNOBSERVABLE**. Keep his paths exclusive. Operate only on explicitly GPT-owned PR or genuinely disjoint new branch, per current owner authorization and #15. Never infer process death from GitHub silence alone.
3. Pin task ID, change paths and immutable base; use own branch `assurance/gpt-<task>`, draft PR, smallest patch. All ref updates must be fast-forward and CAS with `expected_sha`. Never force or directly push `main`.
4. Before every push/merge re-fetch main, PR head, other agents' updates and ownership. On drift/collision: STOP, reconcile; never overwrite another writer.

## 2. Technical falsification (RED → GREEN → MUTATION)

- **RED:** exact revision, stated assumptions, minimal reproducible adversarial input, negative observable behavior and repeatable test oracle. Historical risk alone is not a current defect.
- **GREEN:** minimal correction preserving `/api/lead`, CRM HMAC, durable outbox, quoting/catalog and two CSS themes. Run exact-head GitHub CI; do not claim local tests if only GitHub connector was used.
- **NEGATIVE CONTROL:** mandatory tests remain present by stable full `classname/name` identity; critical mutants killed; 1 physically untestable mutation remains explicit, not silently counted PASS.
- **EVIDENCE:** preserve raw logs, checkout SHA, event/attempt, ZIP provider digest, JUnit, mutation, PNG/HTML hashes, measured synthetic timing and server/receiver outcome. Refuse stale, missing, ambiguous, truncated or rerun-in-flight roles.

## 3. Gate matrix: use actual workflow event + exact SHA

`pull_request`: Quality + HTTP + Visual + Security + measured ≥1800s Soak, only if configured for changed paths. Do not invent PR-specific closure if path-filtered. `push(main)`: Quality + HTTP + Visual + Security + Soak + read-only Evidence Closure when configured. Any missing applicable required run, in-progress job, failure, unexpected skip, mismatched checkout, or drift means **HOLD**.

Main artifacts (as dictated by current `config/evidence-policy.json`, not a fixed report claim): release, mobile, HTTP, visual, OSV, static, soak, mutation, SAST plus ancillary meta/closure when generated. Independently authenticate provider role/run/attempt and re-hash original downloaded ZIP SHA-256, reject unsafe ZIP paths/duplicate entries, check CRC, verify mandatory JUnit identities and no errors, confirm scoped mutation outcomes, 32 image files and PNG CRC, and recompute raw synthetic latency percentiles/ACK/idempotency. Re-check run attempts before manifest publication; a rerun TOCTOU invalidates capture. Never silently use a previous SHA's successful results.

Full canonical chain (command flags are versioned: inspect `--help` at the actual HEAD): `tools/evidence_collect.py` → `tools/meta_evidence_gate.py` → `tools/evidence_reconcile.py --close` → `tools/assurance_check.py --require engineering`. Run only in a disposable workflow/checkout with authenticated artifacts and stable SHA. Never fabricate or directly edit generated ledger status.

## 4. PR readiness / merge / post-merge

All required current-PR HEAD Actions must be `SUCCESS` (with only explicitly allowed skips), no unresolved critical defects, independent raw provider bytes/provenance checked, no competing Opus change, and source base compatible. Only then change DRAFT→READY and guardedly merge with `expected_head_sha`. Re-fetch actual merged main/tree and require **new exact-main workflows**, **new original ZIPs** and **new read-only closure** before marking the new SHA source-accepted. A PR diff that only adds docs still creates a new SHA; its previous acceptance cannot transfer.

## 5. Decision taxonomy and operational boundary

- `VERIFIED`: complete source-bound raw evidence and passing mandatory oracle for that specific claim and SHA.
- `BLOCKED_EXTERNAL`: signed/authorized owner, legal, host, receiver, rights or field proof unavailable; do not manufacture it.
- `UNKNOWN`: proof not measured, role incomplete/ambiguous, receipt missing or untrusted.
- `ENGINEERING_ACCEPTED_LOCAL_PROOF_ONLY`: qualified software assurance, *never* deployment authority.
- `PRODUCTION_HOLD`: keep until C0/C10, B1–B9, external R/H/F/S/D receipts and an explicitly authorized exact-SHA rollout are independently satisfied.

Persist only material issue #15 checkpoint (UTC, main/head SHA, task ID, owned paths, run/attempt IDs, provider hashes, verified state, next step); no duplicative status spam. Never touch real CRM, passwords, PII, live DNS/TLS or deployments under this protocol.
