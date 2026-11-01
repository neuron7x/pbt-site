# Assurance: what this system guarantees, and under which assumptions

Machine-readable sources: `assurance/ledger.json` (48 obligations), `assurance/case.json` (claims C0–C10),
`assurance/threat-model.json`, `assurance/controls.json`, `config/mutation-catalog.json`.
Decide with `make assurance`. Reject falsified evidence with `tools/meta_evidence_gate.py`.
A merged PR is not a deployment. Production state: see `docs/PRODUCTION_HOLD.md`.

## Safety properties

Tested with falsifiers on real processes. Finite tests are evidence, not proof.

| Property | Holds when | Falsifier |
|---|---|---|
| HTTP 201 implies a durable lead with all its outbox rows | SQLite on a local filesystem, `synchronous=FULL` | SIGKILL at six cutpoints (`test_data_integrity.py`) |
| Same key + same normalized payload → same lead; different payload → 409, never replacement | across concurrency and restart | 32 concurrent posts through two processes; 60-step seeded walks with crashes (`test_stateful_model.py`) |
| An invalid or truncated request leaves no state | always | `test_http_protocol.py`, full-disk injection |
| No orphan outbox row can be written | every connection from `db()` | read-back of the pragma, orphan insert |
| A legacy anomaly is reported, never repaired or deleted | startup, restore | `test_legacy_orphan_is_reported_never_repaired_and_never_lost` |
| Interrupted restore leaves the old or the new database usable at its path | process death and ENOSPC/EIO at every discovered filesystem step | `test_restore_cutpoints.py` |
| Stale sidecars never roll back into a restored database | same | hot-journal fixture |
| A lost response followed by a reload replays the same lead | same tab, within 30 minutes, secure context, unchanged content | `test_lead_reload_idempotency.py` |
| A signed body never follows a redirect | always | `test_redirect_does_not_forward_webhook_hmac_to_other_host` |
| Readiness never exceeds what it observed | always | `test_readiness_truth_table.py` |

## Liveness, conditional

A pending outbox row reaches `delivered` or `failed` **if** the server runs, the worker thread is scheduled and
the receiver answers within the deadline often enough. A finite run shows this for its own conditions only.
`delivered` means a 2xx at transport level. It is not receiver persistence, and neither is business processing.
Delivery is at least once: a crash after the remote ack redelivers the same id, and deduplication is the receiver's job.

## What is deliberately not guaranteed

- **Power loss ordering.** The crash model is SIGKILL, which keeps the page cache. The directory fsyncs in restore and
  backup are correct by construction but untested: mutant `M-DB-06-dir-fsync` is recorded `UNTESTABLE`, it would need a
  block-layer fault injector.
- **Zero RPO.** A snapshot does not contain later leads. Restore refuses a known gap unless told otherwise, and even then
  raises the id counter without returning the lost leads.
- **Quota across restarts.** Rate limits are in memory and reset when the process restarts. A second server on the
  same database is refused (`single_process_guard`), so the limit holds per process lifetime on one host.
- **Filesystem isolation of the current user unit.** Measured on Ubuntu 24.04: `ProtectHome` and `ProtectSystem` under
  `systemd --user` do not block home read or write (`ops/sandbox_probe.py --manager user` → FAIL), while cgroup limits
  and `NoNewPrivileges` hold. The candidate `ops/systemd/system/pbt-site.service` → PASS. Installing it is a deployment decision.
- **Duplicate intent after 30 minutes or in a new tab.** That is a new request by definition, and the same content becomes a second lead.
  On plain HTTP `crypto.subtle` is absent, and idempotency falls back to memory only.
- **WCAG conformance, ASVS conformance, a SLSA level, field Core Web Vitals.** Selected controls are in `assurance/controls.json`,
  and each claim names its test. Lab LCP/CLS are a regression probe with three samples, not a distribution. INP is null.
- **Low-severity scanner findings** are not gated. JavaScript has no taint analysis: `tools/dom_sinks.py` is an
  inventory that forces review of a new sink, and it cannot prove a reviewed sink safe.

## Evidence chain

```
tools/evidence_collect.py    GitHub API: runs, jobs, artifact ids, provider digests; bytes checked, digest refetched
        ↓ manifest + ZIPs
tools/meta_evidence_gate.py  offline: exact SHA, repository, target event, every required job completed, required test
                             identities, raw percentiles against budgets, PNG CRC, mutation verdicts recounted against
                             the whole catalog, OSV findings from raw output, SBOM and provenance revision
        ↓
tools/evidence_reconcile.py  the only promotion path: each obligation bound to JUnit cases that ran and passed, and to a
                             mutant killed at that revision; writes receipts, ledger and case
        ↓
tools/assurance_check.py     --require engineering: recomputes all of the above from the ZIPs and derives every claim;
                             a status written in a file can only agree with the derivation, never cause it
```

Roots of trust this chain does not remove: the GitHub API answer under the operator's token, and the runner it describes.
Build-platform signing is absent. A receipt proves consistency with what the provider reported.

| Decision | Exit | Meaning |
|---|---|---|
| `SCHEMA_VALID` | 0 | Ledger and specification are well formed. Accepts nothing. Used in CI during development. |
| `ENGINEERING_ACCEPTED` | 0 | C1–C9 derived PASS from real artifact bytes at a compatible revision. |
| `PRODUCTION_ELIGIBLE` | 0 | Also every external class signed by an authorized owner key. Still not a deployment. |
| `PRODUCTION_HOLD` | 3 | Engineering accepted; external receipts missing. |
| `EVIDENCE_REJECTED` | 1 | Forged, stale, missing or inconsistent. |

Evidence states are distinct: listed by GitHub → ZIP bytes downloaded → digest and CRC checked → content validated →
claim survived negative controls. Only the last supports a verdict.

Artifact categories are not interchangeable. `assurance/source/` is the normative specification, pinned by digest in
`tools/assurance_check.py`. Only `assurance/evidence/`, the promoted fields of `assurance/ledger.json` and
`assurance/case.json`, `docs/` and `README.md` may change after measurement. Changing a test, tool, config, threat model or
the ledger's contract fields voids the proof (`proof_void_changed_*`). `make assurance` keeps working through such changes,
and a code PR simply reopens the ledger: stage `pre_integration`, technical leaves `UNKNOWN`.

External facts close only with a detached SSH signature from a key in `config/owner-allowed-signers`, which is deliberately
empty: `tools/external_receipts.py`. A signature proves who stated a fact, not that it is true.

**Governance limit.** `main` is not protected: branch protection and rulesets return HTTP 403 on this plan for a private
repository (`gh api repos/neuron7x/pbt-site/rulesets`). CI cannot block a direct push. Admission is discipline: PR, exact-head
receipts, `--match-head-commit`. It is enforceable only by a plan upgrade, which is the owner's decision.

```sh
python3 tools/evidence_collect.py --kind push --head "$MAIN" --base "$PARENT" --out evidence/
python3 tools/assurance_check.py --require engineering --evidence-dir evidence/
```

## Backup and restore failure model

| Failure | Covered | How |
|---|---|---|
| Process death at any filesystem step of restore or backup | Yes | SIGKILL before and after each discovered operation |
| ENOSPC or EIO at any filesystem step of restore | Yes | Injected at each operation |
| Two backups at once | Yes | Kernel lock; second exits 2; deterministic barrier test |
| A server running on the database during restore | Yes on one host | Same lock as the server; a refused server writes nothing |
| Power loss, torn sectors, reordered writes | **No** | `M-DB-06-dir-fsync` is UNTESTABLE here. No isolated block device was used. fsync order is by reasoning only |
| Disk or machine loss | **No** | Snapshots are local. R1 and R2 in `docs/PRODUCTION_HOLD.md` |
| Leads after the last snapshot | **Lost** | Reported as `known_RPO_gap`; never presented as recovered |

## When the claims expire

Evidence is valid for its revision. After any executable change, collect new exact-main receipts:
`gh workflow run` for the four dispatch workflows; the soak runs on push when its paths change, otherwise by dispatch. Then
`tools/evidence_reconcile.py --close`.

## Install, test, build

```sh
python3 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements.txt
.venv/bin/python -m playwright install --with-deps chromium webkit
PY=.venv/bin/python make gate        # full suite, offline bundle, media budget, clean tree
PY=.venv/bin/python make mutation    # critical faults on a disposable copy
PY=.venv/bin/python make assurance   # ledger well-formed; accepts nothing
```
Python 3.12 and the versions in `requirements.txt`; no runtime dependency beyond the standard library and system tzdata.

## Operations

```sh
python3 ops/readiness.py --max-pending-age-s 600 --max-worker-idle-s 60 [--receiver-receipt r.json]  # exit 0/1/2
python3 ops/incident_correlate.py event.json      # monitor event vs local signals; UNKNOWN stays UNKNOWN
python3 ops/backup.py                             # online snapshot, integrity check, atomic publish
python3 ops/restore.py SNAPSHOT --min-seq N       # stop the server first; exit 2/3/4 are refusals
python3 ops/restore_drill.py SNAPSHOT --external-watermark N   # measures RTO and RPO gap; touches nothing live
python3 ops/sandbox_probe.py --manager user       # measures which sandbox boundaries really hold
```

The thresholds above are operator input, not adopted SLOs. Rollback of code: deploy the previous `main` SHA; the
schema change here is additive and old code runs on the migrated database. Rollback of data: `ops/restore.py`, and the
previous database is preserved as `<db>.pre-restore-<stamp>`. No rollback has been rehearsed on a production edge.
