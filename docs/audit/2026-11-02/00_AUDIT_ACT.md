# PBT Site — Independent Engineering Audit Act (2026-11-02)

**Repository:** `neuron7x/pbt-site` (private)\
**Immutable audit target:** `main@382a476b3803f03a8dd1de53c69931f551719151`\
**Scope:** repository source tree, existing machine-readable contracts, current GitHub Actions run/job/artifact *metadata*, open issues, historical PRs, and primary technical standards.\
**Out of scope / not observed:** deployment host and keys, private CRM instance, external receiver, CDN/DNS/TLS edge, live user journeys, iOS hardware, authenticated customer permissions, actual owner decisions, download + independent hashing of all Actions ZIP bytes.\
**Decision:** SOURCE IMPLEMENTATION WITH FIVE GREEN EXACT-HEAD WORKFLOWS; INDEPENDENT ENGINEERING ACCEPTANCE **NOT RECORDED**; PRODUCTION **HOLD**.

## A. Evidence classification — non-negotiable

- `API_OBSERVED`: fetched from authenticated GitHub repository / Actions metadata; authenticity depends on the authenticated provider account.
- `SOURCE_OBSERVED`: byte/text inspection of repository at target SHA. Does not imply correct runtime behavior.
- `CI_REPORTED_SUCCESS`: authenticated Actions run and jobs state `success`; not independently rerun, does not certify completeness of oracles.
- `INDEPENDENT_ARTIFACT_VERIFIED`: requires the **actual ZIP bytes** + provider digest, SHA256, ZIP/PNG CRC, raw JUnit, negative tests, pinned target SHA; **NOT PERFORMED IN THIS AUDIT**.
- `FIELD_VERIFIED`: observed on the approved target host, real receiver, authorized users and devices; **NOT PERFORMED**.
- `HISTORICAL_RISK`: a finding from a prior source revision; it must be re-tested against current SHA before becoming a live issue.
- `ASSUMPTION`: explicit engineering hypothesis pending a falsification run; must not be promoted to a defect or PASS.

Never use a green workflow, a code comment, a self-reported README, or a successful synthetic test as a substitute for external production evidence.

## B. Verified inventory

- Latest main `382a476b3803f03a8dd1de53c69931f551719151`; 364 Git blobs; 393 Git tree entries; the tree was not truncated; 119,897,087 total blob bytes. Repo reported historical size 405,983 KB (NOT the current deploy payload).
- Five workflow YAMLs; 66 `tests/test_*.py` files; 27 Python source tools; `assurance/source/tasks.json` lists 48 normative tasks in six waves W0..W5.
- `assurance/ledger.json`: 30 `IMPLEMENTED/INFERRED`, 18 `BLOCKED/UNKNOWN`; stage `pre_integration`.
- `assurance/case.json`: 10 top-level claim groups C1..C10; all 29 claim leaves `UNKNOWN`.
- `assurance/source/risks.json`: 24 historical risk hypotheses **NOT** 24 currently demonstrated code defects.
- Active issues: #4 (dual theme), #6 (runtime & external tracks), #15 (AECC control plane). PRs: 0 open; 17 historical PRs closed, PR #20 merged 2026-11-02.
- User-facing site: nine semantic sections in `web/index.html`; two themes, responsive HTML/CSS, animation + Canvas + scroll-linked video logic; 32 fleet entries, 8 categories and 8 material entries in `data/catalog.json`.
- `web/media/video`: 14 MP4 + 14 WebM + 14 poster WebP; `web/media/cine`: 12 MP4 + 12 WebM + 12 posters. These are encoded renditions, NOT 52 distinct commissioned shoots.
- `server/app.py` supports `/api/lead`, `/api/health`, `/api/config`, SQLite durable lead/outbox, idempotency key, configured Telegram / HMAC webhook; `ops` contains backup, restore, readiness and process-unit tools.
- Direct source inspection confirms newer mitigations: `PRAGMA foreign_keys=ON` + readback, `PRAGMA synchronous=FULL`, atomic transaction; `ops/restore.py` uses atomic `os.replace` and directory fsync controls; `web/js/site.js` saves short-lived per-tab idempotency state; `tools/meta_evidence_gate.py` no longer hard-codes PR #8. Historical R01/R02/R06/R08 should NOT be reopened without a current failed oracle.
- Latest exact-HEAD workflows (all reported `success` on this SHA):
  - Quality + full gate: https://github.com/neuron7x/pbt-site/actions/runs/41419498479
  - Synthetic 1800+ s soak: https://github.com/neuron7x/pbt-site/actions/runs/41419498548
  - Visual evidence: https://github.com/neuron7x/pbt-site/actions/runs/41419498347
  - Transport: https://github.com/neuron7x/pbt-site/actions/runs/41419498449
  - Locked dependency vulnerability assurance: https://github.com/neuron7x/pbt-site/actions/runs/41419498560

These reports confirm that the workflows executed and succeeded. Their raw ZIP contents and the complete claim graph are NOT independently accepted here.

## C. Material open gaps and dispositions

| ID | Priority | Evidence classification | Observed fact / bounded conclusion | Required falsifier or receipt | Owner |
|---|---|---|---|---|---|
| A-01 | P1 | SOURCE_OBSERVED | `case.json` claims C1..C10 remain UNKNOWN; `ledger.json` has no promoted technical PASS | Fetch current 9 required push roles + authenticated raw ZIP bytes, rehash/replay, run `evidence_reconcile.py --close`, then `assurance_check.py --require engineering` | Engineering |
| A-02 | P1 | API_OBSERVED | `main.protected=false`; a direct push can bypass source admission policy | Require enforceable branch ruleset/protection or document unmitigated governance hazard and exact-head checks | Owner/GitHub |
| A-03 | P1 | FIELD_UNVERIFIED | Actual production receiver/CRM persistence, dedup, TLS/proxy and secret configuration unknown | Redacted receiver-side receipt with real persisted IDs and independent edge test | Owner/operator |
| A-04 | P1 | EXTERNAL_BLOCKED | Current tariffs, VAT, idle, crane/dispatch rules NOT approved; historical JS220 1,350 vs 1C 2,700 UAH/h discrepancy | Effective-dated owner-signed tariff snapshot + independently recomputed quote tests | Owner |
| A-05 | P1 | EXTERNAL_BLOCKED | Privacy purpose, lawful basis, retention and approved notice missing | Legal owner decision + retention implementation and delete/backup reconciliation proof | Owner/lawyer + engineering |
| A-06 | P1 | EXTERNAL_BLOCKED | Customer footage rights and third-party Wikimedia attribution / brand usage approvals absent | Per-file rights/license receipts by authorized owner | Owner |
| A-07 | P1 | EXTERNAL_BLOCKED | Off-device encrypted backup and separate-host recovery with RPO/RTO not demonstrated | Provider storage receipt, crypto/digest, separate-host disaster drill, issued-ID watermark | Owner/operator |
| A-08 | P1 | SOURCE_OBSERVED | `docs/RELEASE_STATUS.md` and `docs/OWNER_DECISIONS.md` cite October-only older HEAD / test numbers | Immutable-current-status generated view; keep past evidence historical, no manual overwrite of normative task snapshots | Engineering |
| A-09 | P1 | SOURCE_OBSERVED | `config/owner-allowed-signers` empty by design; external evidence cannot be signed/accepted | Owner provisions identity/allowed signers outside agent autonomy, validates authenticity/expiry | Owner |
| A-10 | P1 | API_OBSERVED | Provider workflow green != independent ZIP/CRC/JUnit/PNG/latency byte verification | Execute current exact-main provider artifact verification; refusal on missing or tampered member | Engineering |
| A-11 | P2 | SOURCE_OBSERVED | `references/` media inputs untracked; byte-for-byte rebuild from Git tree alone cannot be asserted | Recreate from authorized/hash-pinned supplied sources, compare actual exported bytes & tool versions | Engineering/owner |
| A-12 | P2 | LAB/FIELD GAP | Lab LCP/CLS, media budgets and video fallbacks exist; no p75 real-user INP/CWV or stable field exposure | Authorized privacy-safe field collection with segment, window, p75 & uncertainty | Owner/operator |
| A-13 | P2 | LAB/FIELD GAP | WCAG automated tests do not establish full conformance, real screen-reader / iOS/Android behavior | W3C WCAG-EM 2.0 evaluation of both themes and video states, manual assistive-tech matrix | Independent evaluator |
| A-14 | P2 | SOURCE_OBSERVED | No `robots.txt`, `sitemap.xml`, deployed authoritative `rel=canonical` present in current tree | Confirm FQDN and SEO strategy; check deployed indexability and canonical metadata | Owner/engineering |
| A-15 | P2 | SOURCE_OBSERVED | Source asset inventory exceeds 110 MB, and media thresholds are regression budgets, not a delivery-SLA | Cold/warm mobile traces, real transferred bytes and video decoder CPU/memory across profiles | Engineering |
| A-16 | P2 | SCOPE_LIMIT_CONFIRMED | Scoped AST scan/locked Python audit != broad SAST/DAST or SLSA conformance | Threat-driven coverage map; pinned SAST + authorized DAST; signed provenance verification | Security engineering |
| A-17 | P2 | EXTERNAL_BLOCKED | `systemd --user` sandbox boundaries insufficient per documented Ubuntu probes | Adopt/test dedicated system identity and host kernel restrictions on target | Owner/operator |
| A-18 | P2 | EXTERNAL_BLOCKED | Production SLO, alert escalation, DR acceptance & deployment authorization missing | Adopt policy before field measurement, rehearse rollback, sign exact SHA receipt | Owner/operator |
| A-19 | P2 | CODE_REVIEW_NEEDED | Config-to-DOM sinks / URL trust; old risk R15 conditional, not proof of XSS | Adversarial DOM data vectors, CSP checks, browser execution instrumentation | Engineering |
| A-20 | P2 | SCOPE_DECISION | Full CMS, user accounts, checkout, SEO landing pages, live asset availability are NOT currently contracted in this repo | Only start after new written requirements and business ROI; never confuse scope expansion with code defects | Owner |

No P0 exploitable vulnerability is claimed without a concrete reproducible counterexample. `A-01` is a proof/acceptance gap; `A-02` is a governance exposure, not evidence of malicious modification. External facts are not repairable by agents inventing data.

## D. Risk control: reconcile historical findings, do not clone them

- R01/R02/R06/R07/R08/R19: original risk documents predate merged fixes; audit the implemented current tests, failed mutation controls and exact-HEAD artifacts before reclassifying. R19's older "missing main soak" is superseded by current exact-main success metadata.
- R03/R04/R09/R10/R11/R12/R13/R21/R23/R24: external/instrumentation uncertainties remain real but must not be called proven exploitable code bugs.
- R05/R14/R16/R17/R18/R20/R22: bounded-scope/conditional limitations; validate under declared topology, not via slogans.
- The primary source specification `assurance/source/*.json` may be intentionally sealed; do not rewrite its original `NOT_EXECUTED` values to "green". Maintain a separately derived release-state projection.

## E. Decision table and authorization boundaries

| State | Required evidence | Current decision |
|---|---|---|
| `SCHEMA_VALID` | JSON structure and source spec well formed | Allowed as a narrow schema claim |
| `CI_REPORTED_GREEN` | All five exact-main workflows success | YES, GitHub metadata |
| `ENGINEERING_ACCEPTED` | Authentic raw artifacts, mandatory test identities, independent CRC/raw sample reconciliation, killed critical mutants and compatible source SHA, all mandatory engineering leaves PASS | **NOT ESTABLISHED** |
| `PRODUCTION_ELIGIBLE` | Engineering PASS + valid authorized B1–B9/R1–R3/H1/F1/S1/D1 external receipts, field boundaries | **NO — HOLD** |
| `DEPLOYED` | Separate, explicit authorized deployment with live endpoint and rollback receipts | **NOT OBSERVED** |

This audit does **not** require a second human code-review gate for the solo engineering workflow. It does require real owner/legal/operational facts where an automated witness cannot create them.

## F. Relevant existing controllers

- https://github.com/neuron7x/pbt-site/issues/4 — two themes and visual acceptance.
- https://github.com/neuron7x/pbt-site/issues/6 — T1..T7 operating tracks.
- https://github.com/neuron7x/pbt-site/issues/15 — AECC agents, evidence and handoff policy.
- `docs/audit/2026-11-02/01_TASK_REGISTER.md`: authoritative 48-item status projection plus new audit actions.
- `docs/audit/2026-11-02/02_EXECUTION_AND_ACCEPTANCE.md`: sequencing, protocols, artifacts.
- `docs/audit/2026-11-02/03_AGENT_PROMPTS.md`: bounded independent agent instructions.
- `docs/audit/2026-11-02/04_PRIMARY_SOURCES.md`: versioned first-party standards.

**Non-authorization:** This act itself does not merge, deploy, edit CRM, authorize media, approve tariffs, sign receipts or claim legal compliance.
