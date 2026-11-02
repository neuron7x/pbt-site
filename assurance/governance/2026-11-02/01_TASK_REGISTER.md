# PBT · Task Register / 48 normative obligations

**Kind:** dated, non-normative execution projection · **Source SHA:** `dd85775749e28cf35c2e0c80c188b5dfbda21add` · **Canonical inputs:** `assurance/source/tasks.json` (sealed W0–W5), `assurance/ledger.json` (actual pre-integration state). **DO NOT overwrite normative task or status records using this document.**

**Census from source, not estimation:** 48 tasks, 30 `IMPLEMENTED/INFERRED`, 18 `BLOCKED/UNKNOWN` in committed ledger. Prior source-scoped GitHub closure at this SHA reported 30 VERIFIED + 18 BLOCKED_EXTERNAL; original committed `assurance/ledger.json` remains `pre_integration`. Proof is revision-bound and does **not** transfer to this documentation PR or any future HEAD.

**Routing:** [#21 — backlog](https://github.com/neuron7x/pbt-site/issues/21); [#15 — handoff](https://github.com/neuron7x/pbt-site/issues/15); [#6 — operational tracks](https://github.com/neuron7x/pbt-site/issues/6); [#4 — visual](https://github.com/neuron7x/pbt-site/issues/4). Each obligation below carries its original *RED falsifier*, dependency, and executable acceptance predicate. `BLOCKED` is an unresolved external dependency, not an instruction to manufacture a receipt.

## W0 · Assurance / immutable evidence (8)

| Task / priority | Required change | Committed status | Depends on | Counterexample (RED) | Acceptance oracle |
|---|---|---|---|---|---|
| **EVD-01** · P1 | Freeze immutable revision, baseline and original artifacts | `IMPLEMENTED/INFERRED` | none | Compare GitHub head/base/runner SHA with stale or swapped SHA | Any drift causes HOLD before further gate; baseline environment and real bytes captured |
| **EVD-02** · P1 | Generalize PR8-only meta evidence policy | `IMPLEMENTED/INFERRED` | EVD-01 | Present valid PR14/main evidence to old PR8-only verifier; require negative failure | Valid current HEAD accepted, stale/forged/unsupported event rejected with machine-readable reason |
| **EVD-03** · P2 | Assert compulsory test identities and minimum coverage | `IMPLEMENTED/INFERRED` | EVD-02 | Remove lead atomicity test while retaining >= MIN_TESTS total | Mandatory test identity absent => FAIL regardless total count; no silent skip/xfail |
| **EVD-04** · P1 | Independent mobile budgets and CLS adjudication | `IMPLEMENTED/INFERRED` | EVD-02 | Present raw p75 LCP above 2500 while consistent summary claims success | Independent verifier fails for any breach; no field INP claim |
| **EVD-05** · P1 | Bind event SHA, checkout HEAD and artifact source | `IMPLEMENTED/INFERRED` | EVD-01, EVD-02 | Substitute merge event SHA as execution_sha or re-run with changed base | Verifier rejects drift; PR and main receipts remain disjoint |
| **EVD-06** · P1 | Independently verify provider ZIP bytes and manifests | `IMPLEMENTED/INFERRED` | EVD-01, EVD-02 | Modify one PNG chunk/ZIP CRC/manifest SHA, preserve workflow success | All required artifacts checked; failures remain HOLD; provider authentication provenance recorded |
| **EVD-07** · P2 | Reproducibility and nondeterminism inventory | `IMPLEMENTED/INFERRED` | EVD-01 | Run same fixed seed twice with locale/timezone/env variance | Every difference classified; source build reproducibility not asserted if unverified |
| **EVD-08** · P1 | Construct reusable claim-argument-evidence graph | `IMPLEMENTED/INFERRED` | EVD-02, EVD-03, EVD-04, EVD-05, EVD-06 | Supply a complete list with one unavailable proof | Claim is PASS iff all mandatory proof leaves PASS at compatible SHA and target |

## W1 · SQLite, idempotency, backup (8)

| Task / priority | Required change | Committed status | Depends on | Counterexample (RED) | Acceptance oracle |
|---|---|---|---|---|---|
| **DB-01** · P1 | Enable FK enforcement per SQLite connection | `IMPLEMENTED/INFERRED` | EVD-01 | Insert outbox with nonexistent lead_id; currently SQLite FK not enabled in db() | Every write path rejects orphan with IntegrityError; foreign_key_check reports zero after approved remediation |
| **DB-02** · P1 | Migration and legacy-FK compatibility proof | `IMPLEMENTED/INFERRED` | DB-01 | Legacy database includes old schema and an intentionally orphaned row | Repeated migration exact schema; no data loss; conflicts report BLOCKED and do not quietly repair |
| **DB-03** · P1 | Linearizable idempotency and quota transaction | `IMPLEMENTED/INFERRED` | EVD-01 | Concurrent same key across threads/processes under near-capacity SQLite locking | Same key + same body -> same id; same key + different body -> 409; accepted state atomic |
| **DB-04** · P1 | Crash cutpoints around HTTP 201 and durable commit | `IMPLEMENTED/INFERRED` | DB-03 | SIGKILL at before BEGIN/after insert/before commit/after commit/before reply | For all cuts: no uncommitted 201, no lost committed lead, replay consistent |
| **DB-05** · P2 | Cross-reload client idempotency without PII retention | `IMPLEMENTED/INFERRED` | DB-03, DB-04 | Accept server-side, drop response, reload and submit unchanged form | Replay semantics preserved if same user intent; explicitly documented boundary for new intent |
| **DB-06** · P1 | Crash-safe restore generation and rollback | `IMPLEMENTED/INFERRED` | DB-02, DB-04 | SIGKILL/EIO/ENOSPC at each rename/fsync and metadata operation | No scenario produces irrecoverable partial state; old/new integrity and watermark checked |
| **DB-07** · P1 | Authenticated encrypted off-device backup chain | `BLOCKED/UNKNOWN` | DB-06 | Destroy local root/data and backup directory in a disposable isolated environment | Provider receipt + offline restore verified against source snapshot; local-only copies not counted |
| **DB-08** · P1 | Independent host restore, watermark and RPO/RTO measurement | `BLOCKED/UNKNOWN` | DB-06, DB-07 | Delete original machine and restore without source disk or server.log | No unreconciled known loss; actual RPO/RTO numbers and limitations recorded; owner adopts thresholds |

## W2 · Transport / security / trust (8)

| Task / priority | Required change | Committed status | Depends on | Counterexample (RED) | Acceptance oracle |
|---|---|---|---|---|---|
| **NET-01** · P1 | HTTP parser absolute deadlines and protocol negative suite | `IMPLEMENTED/INFERRED` | EVD-01 | Trickled headers/body, early EOF, conflicting length, media range fuzz under small MAX_CONNECTIONS | Bound wall-clock and connection slots, correct status class, zero partial commits |
| **NET-02** · P1 | Reverse proxy trust and TLS edge attestation | `BLOCKED/UNKNOWN` | NET-01 | Spoof XFF/XFP from untrusted peer; spoof chain and IPv6 identities | No quota bypass/false HSTS with untrusted headers; actual edge evidence separate |
| **NET-03** · P2 | Constrain outbound destinations and redirects | `IMPLEMENTED/INFERRED` | NET-01 | Hostile redirects, private-IP targets, DNS rebinding, non-TLS and credentials in URL | No signed lead crosses unapproved destination; synthetic tests isolate external network |
| **NET-04** · P1 | At-least-once channel/receiver contract and acknowledgment | `BLOCKED/UNKNOWN` | DB-03, DB-04 | Synthetic 2xx before durable receiver acknowledgment; 408/429/5xx and timeout | No accepted lead lost; retries bounded; all ACK claims tied to external receipt ID |
| **NET-05** · P2 | Rate limit topology, clock and resource accounting | `IMPLEMENTED/INFERRED` | NET-01 | 25k identities, IPv6 /64 churn, wall jumps, two independently spawned servers | No unbounded memory nor quota bypass within declared topology; unsupported topology fail closed |
| **NET-06** · P1 | Config to DOM trust-boundary and XSS negative suite | `IMPLEMENTED/INFERRED` | EVD-01 | Inject malformed href, quotes, svg/javascript schemes via fake public config | All payloads inert, console signals captured, CSP intact, negative mutation kills regression |
| **NET-07** · P2 | Broaden security scanning and dependency provenance | `IMPLEMENTED/INFERRED` | EVD-06 | Inject XSS/SSRF-like sink, scanner crash, omitted requirement, altered wheel hash | Findings and gaps machine reported; waiver requires owner rationale; no full ASVS certification claim |
| **NET-08** · P2 | Least privilege and resource sandbox of site runtime | `BLOCKED/UNKNOWN` | NET-01 | Attempt to read files outside sandbox, exhaust tasks/memory, abuse writable root | Resource caps and file/network boundaries proven, no break of media/API/backup |

## W3 · UX / accessibility / content (8)

| Task / priority | Required change | Committed status | Depends on | Counterexample (RED) | Acceptance oracle |
|---|---|---|---|---|---|
| **WEB-01** · P1 | Manual + automated WCAG matrix across both themes | `BLOCKED/UNKNOWN` | EVD-04 | Focus traps, enlarged text 200%, empty labels, error states, modal mode | No critical WCAG A/AA finding; manual evidence named; axe alone never claimed complete |
| **WEB-02** · P1 | Independent full lab CWV repeatability | `IMPLEMENTED/INFERRED` | EVD-04 | Force slow LCP or late shift while internally consistent summary says PASS | Independent budget violation rejects; field INP remains unknown |
| **WEB-03** · P1 | Field INP/CWV with privacy-respecting RUM or CrUX | `BLOCKED/UNKNOWN` | WEB-02 | Inject long input tasks into critical user flow | Measured p75 by mobile/desktop meets owner-approved objectives or release HOLD |
| **WEB-04** · P2 | Theme switch stability, contrast under dynamic media | `IMPLEMENTED/INFERRED` | WEB-01, WEB-02 | Load font after 500ms, dark/bright sampled frames, extreme landscape viewport | Any unprompted shift/contrast violation rejected at measured state with raw screenshots |
| **WEB-05** · P2 | Critical media and network budget as a regression contract | `IMPLEMENTED/INFERRED` | WEB-02 | Add unexpected high-priority video/font preload or corrupt poster | Per-profile transfer budgets from measured baseline; no broken poster or blank hero |
| **WEB-06** · P2 | Canonical metadata, SEO indexability, authoritative FQDN | `BLOCKED/UNKNOWN` | OPS-07 | Change canonical, og image or JSON-LD to mismatched domain | Canonical/schema/OG agree with owner-approved DNS+TLS; search indexing cannot be asserted absent field proof |
| **WEB-07** · P1 | Business/contact and tariff single-source consistency | `BLOCKED/UNKNOWN` | EVD-03 | Make JCB rate or VAT differ across JSON/JS/HTML while math still passes | No unapproved published rate or hidden VAT semantics; arithmetic independent oracle passes |
| **WEB-08** · P1 | Media licensing/provenance and true-claim inventory | `BLOCKED/UNKNOWN` | EVD-01 | Remove permission record for one video while bytes/hash remain valid | Every release asset has matched source rights and owner authorization; unresolved rights block publication |

## W4 · SRE / business / legal (8)

| Task / priority | Required change | Committed status | Depends on | Counterexample (RED) | Acceptance oracle |
|---|---|---|---|---|---|
| **OPS-01** · P1 | Separate liveness, readiness, delivery and business acceptance | `IMPLEMENTED/INFERRED` | NET-04 | Worker heartbeat fresh with 100 stale pending jobs and no receiver ACK | No metric implies greater assurance than observed; unknown/failed channel blocks release |
| **OPS-02** · P1 | Predeclare production SLI/SLO/alert thresholds | `BLOCKED/UNKNOWN` | OPS-01, WEB-03 | Report 100% availability from synthetic soak with no field requests | Adopted pre-run SLO; no backfilled goals; actual monitored values with data-quality bounds |
| **OPS-03** · P1 | Correlate host, power-guard and external monitoring failures | `IMPLEMENTED/INFERRED` | OPS-01 | Trigger false heartbeat DOWN during intentional power guard; real failed sender | Each incident has provider event ID and root-cause status; unknown remains unknown |
| **OPS-04** · P1 | Authorize actual privacy processing and notices | `BLOCKED/UNKNOWN` | EVD-01 | Find contact form with no approved policy and no documented retention authorization | Signed/recorded policy edition and purpose/retention decision or legal HOLD |
| **OPS-05** · P1 | Retention, deletion and backup lifecycle consistency | `BLOCKED/UNKNOWN` | DB-08, OPS-04 | Insert expired and legal-hold records, simulate deletion and restoration from old backup | Data lifecycle verified; no irreversible auto-delete without approved policy |
| **OPS-06** · P1 | Commercial effective-dated rates and quote semantics | `BLOCKED/UNKNOWN` | WEB-07 | Compare 1C external proposed rates with site, inject conflicting quote or rounding | Unknown or conflicting rate => publish HOLD or label explicitly unverified; no unapproved assumptions |
| **OPS-07** · P1 | Domain TLS edge, production rollout and rollback rehearsal | `BLOCKED/UNKNOWN` | NET-02, EVD-08 | Certificate mismatch, wrong DNS target, missing redirect/HSTS, broken new rollout | DNS/TLS/rollback proof and owner authorization separate from source CI |
| **OPS-08** · P1 | Conjunctive owner release acceptance B1–B9 + T1–T7 | `BLOCKED/UNKNOWN` | EVD-08, OPS-02, OPS-04, OPS-05, OPS-06, OPS-07, WEB-08 | Keep one source absent and run green CI | Release PASS iff all mandatory leaves are evidence-verified at target version and owner deploy authorization exists |

## W5 · Adversarial / independent closure (8)

| Task / priority | Required change | Committed status | Depends on | Counterexample (RED) | Acceptance oracle |
|---|---|---|---|---|---|
| **ADV-01** · P1 | Threat model with attack trees and known trust boundaries | `IMPLEMENTED/INFERRED` | NET-03, NET-06 | New data flow bypasses source-sink inventory without requiring update | Every high-impact path linked to at least one test and owner of risk |
| **ADV-02** · P1 | Mutation score on critical safety and integrity contracts | `IMPLEMENTED/INFERRED` | EVD-03, EVD-04, DB-04 | Mutate HMAC verification, FK checks, dedup uniqueness, replay or budget bounds | All designated critical mutants killed; score measured without arbitrary blanket 100% claim |
| **ADV-03** · P1 | Model/state-machine cross-process and temporal fault test | `IMPLEMENTED/INFERRED` | DB-03, NET-05 | Schedule concurrent retry, quota, crash and worker states with fake time | Minimal counterexample recorded; no lost accepted lead or silent invariant breach |
| **ADV-04** · P2 | Extended measured soak with anti-leak and adversarial events | `IMPLEMENTED/INFERRED` | EVD-05, OPS-01 | Inject stuck downstream, server restart, disk pressure, repeated packet faults | Observed duration, integrity, backlog and process samples pass independent checker at same SHA |
| **ADV-05** · P2 | Date/locale/DST, integer precision, and boundary fuzz | `IMPLEMENTED/INFERRED` | WEB-07 | Time-zone offset around DST/day boundary, malformed Unicode and huge integer | All documented boundary cases invariant or explicit rejection; discrepancies fixed or scoped |
| **ADV-06** · P2 | Supply-chain attestations and sandbox anti-tamper | `IMPLEMENTED/INFERRED` | NET-07, NET-08 | Change action pin or wheel hash and replay stale receipt | Mutation rejected; valid source/runner/dependency manifest reproducible within documented limits |
| **ADV-07** · P2 | Real-device accessibility and UI adversarial evaluation | `BLOCKED/UNKNOWN` | WEB-01, WEB-03, WEB-04 | 200% text, high contrast, reduced motion, keyboard only, screen reader, iOS Safari | No unresolved WCAG AA critical failure and recorded field boundary; owner visual approval separate |
| **ADV-08** · P1 | Final assurance case with signed release/no-release decision | `BLOCKED/UNKNOWN` | OPS-08, ADV-01, ADV-02, ADV-04, ADV-06, ADV-07 | Withdraw one mandatory provider receipt after all code gates become green | Zero mandatory unknowns, no new P0/P1, current immutable code proof, owner authorization; otherwise HOLD |

## How to execute without inflating claims

1. Choose one task ID and own only disjoint paths. Re-fetch GitHub `main`/PR status and `AGENTS.md` before every mutation.
2. If `IMPLEMENTED/INFERRED`, do not reopen solely to produce more commits. Prefer canonical `evidence_collect.py` → `meta_evidence_gate.py` → `evidence_reconcile.py` → `assurance_check.py` on actual provider bytes and exact SHA.
3. If a real counterexample fails on current SHA, record RED, smallest source change, GREEN, critical mutation, full exact-head CI and original artifacts. Own branch + draft PR + guarded merge; re-accept **new** main separately.
4. If `BLOCKED/UNKNOWN`, route evidence request in [external act](04_EXTERNAL_EVIDENCE_ACT.md) to legitimate owner, host or field observer. A synthetic test cannot satisfy an external condition.
5. All versioned claims must name `source_sha`, run attempt, artifact IDs and SHA-256. Never claim code-merge = production readiness.

**Unresolved independent release gates:** `C0` and `C10` UNKNOWN; no deployment authorization. See [execution protocol](03_VERIFICATION_PROTOCOL.md).
