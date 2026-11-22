# PBT Site — complete SHA-scoped task and risk register

**Baseline** `neuron7x/pbt-site@382a476b3803f03a8dd1de53c69931f551719151` · 2026-11-02.

**Important:** `assurance/source/tasks.json` is a historical/sealed normative specification. Do not rewrite original `NOT_EXECUTED` statuses; the current `assurance/ledger.json` is a separate status projection, not an independent proof. This document reports both. `IMPLEMENTED/INFERRED` is not `ENGINEERING_ACCEPTED`.

## Normative 48-task census — W0 to W5

### W0 — Assurance spine & exact-source proof

| ID | Title | Priority | Current execution / evidence | Depends on |
|---|---|---|---|---|
| `EVD-01` | Freeze immutable revision, baseline and original artifacts | P1 | IMPLEMENTED / INFERRED | none |
| `EVD-02` | Generalize PR8-only meta evidence policy | P1 | IMPLEMENTED / INFERRED | EVD-01 |
| `EVD-03` | Assert compulsory test identities and minimum coverage | P2 | IMPLEMENTED / INFERRED | EVD-02 |
| `EVD-04` | Independent mobile budgets and CLS adjudication | P1 | IMPLEMENTED / INFERRED | EVD-02 |
| `EVD-05` | Bind event SHA, checkout HEAD and artifact source | P1 | IMPLEMENTED / INFERRED | EVD-01, EVD-02 |
| `EVD-06` | Independently verify provider ZIP bytes and manifests | P1 | IMPLEMENTED / INFERRED | EVD-01, EVD-02 |
| `EVD-07` | Reproducibility and nondeterminism inventory | P2 | IMPLEMENTED / INFERRED | EVD-01 |
| `EVD-08` | Construct reusable claim-argument-evidence graph | P1 | IMPLEMENTED / INFERRED | EVD-02, EVD-03, EVD-04, EVD-05, EVD-06 |

| ID | Counterexample to attempt / mandatory RED test | Acceptance condition |
|---|---|---|
| `EVD-01` | Compare GitHub head/base/runner SHA with stale or swapped SHA | Any drift causes HOLD before further gate; baseline environment and real bytes captured |
| `EVD-02` | Present valid PR14/main evidence to old PR8-only verifier; require negative failure | Valid current HEAD accepted, stale/forged/unsupported event rejected with machine-readable reason |
| `EVD-03` | Remove lead atomicity test while retaining >= MIN_TESTS total | Mandatory test identity absent => FAIL regardless total count; no silent skip/xfail |
| `EVD-04` | Present raw p75 LCP above 2500 while consistent summary claims success | Independent verifier fails for any breach; no field INP claim |
| `EVD-05` | Substitute merge event SHA as execution_sha or re-run with changed base | Verifier rejects drift; PR and main receipts remain disjoint |
| `EVD-06` | Modify one PNG chunk/ZIP CRC/manifest SHA, preserve workflow success | All required artifacts checked; failures remain HOLD; provider authentication provenance recorded |
| `EVD-07` | Run same fixed seed twice with locale/timezone/env variance | Every difference classified; source build reproducibility not asserted if unverified |
| `EVD-08` | Supply a complete list with one unavailable proof | Claim is PASS iff all mandatory proof leaves PASS at compatible SHA and target |

### W1 — Data integrity, idempotency & restoration

| ID | Title | Priority | Current execution / evidence | Depends on |
|---|---|---|---|---|
| `DB-01` | Enable FK enforcement per SQLite connection | P1 | IMPLEMENTED / INFERRED | EVD-01 |
| `DB-02` | Migration and legacy-FK compatibility proof | P1 | IMPLEMENTED / INFERRED | DB-01 |
| `DB-03` | Linearizable idempotency and quota transaction | P1 | IMPLEMENTED / INFERRED | EVD-01 |
| `DB-04` | Crash cutpoints around HTTP 201 and durable commit | P1 | IMPLEMENTED / INFERRED | DB-03 |
| `DB-05` | Cross-reload client idempotency without PII retention | P2 | IMPLEMENTED / INFERRED | DB-03, DB-04 |
| `DB-06` | Crash-safe restore generation and rollback | P1 | IMPLEMENTED / INFERRED | DB-02, DB-04 |
| `DB-07` | Authenticated encrypted off-device backup chain | P1 | BLOCKED / UNKNOWN | DB-06 |
| `DB-08` | Independent host restore, watermark and RPO/RTO measurement | P1 | BLOCKED / UNKNOWN | DB-06, DB-07 |

| ID | Counterexample to attempt / mandatory RED test | Acceptance condition |
|---|---|---|
| `DB-01` | Insert outbox with nonexistent lead_id; currently SQLite FK not enabled in db() | Every write path rejects orphan with IntegrityError; foreign_key_check reports zero after approved remediation |
| `DB-02` | Legacy database includes old schema and an intentionally orphaned row | Repeated migration exact schema; no data loss; conflicts report BLOCKED and do not quietly repair |
| `DB-03` | Concurrent same key across threads/processes under near-capacity SQLite locking | Same key + same body -> same id; same key + different body -> 409; accepted state atomic |
| `DB-04` | SIGKILL at before BEGIN/after insert/before commit/after commit/before reply | For all cuts: no uncommitted 201, no lost committed lead, replay consistent |
| `DB-05` | Accept server-side, drop response, reload and submit unchanged form | Replay semantics preserved if same user intent; explicitly documented boundary for new intent |
| `DB-06` | SIGKILL/EIO/ENOSPC at each rename/fsync and metadata operation | No scenario produces irrecoverable partial state; old/new integrity and watermark checked |
| `DB-07` | Destroy local root/data and backup directory in a disposable isolated environment | Provider receipt + offline restore verified against source snapshot; local-only copies not counted |
| `DB-08` | Delete original machine and restore without source disk or server.log | No unreconciled known loss; actual RPO/RTO numbers and limitations recorded; owner adopts thresholds |

### W2 — HTTP, trust boundaries & security

| ID | Title | Priority | Current execution / evidence | Depends on |
|---|---|---|---|---|
| `NET-01` | HTTP parser absolute deadlines and protocol negative suite | P1 | IMPLEMENTED / INFERRED | EVD-01 |
| `NET-02` | Reverse proxy trust and TLS edge attestation | P1 | BLOCKED / UNKNOWN | NET-01 |
| `NET-03` | Constrain outbound destinations and redirects | P2 | IMPLEMENTED / INFERRED | NET-01 |
| `NET-04` | At-least-once channel/receiver contract and acknowledgment | P1 | BLOCKED / UNKNOWN | DB-03, DB-04 |
| `NET-05` | Rate limit topology, clock and resource accounting | P2 | IMPLEMENTED / INFERRED | NET-01 |
| `NET-06` | Config to DOM trust-boundary and XSS negative suite | P1 | IMPLEMENTED / INFERRED | EVD-01 |
| `NET-07` | Broaden security scanning and dependency provenance | P2 | IMPLEMENTED / INFERRED | EVD-06 |
| `NET-08` | Least privilege and resource sandbox of site runtime | P2 | BLOCKED / UNKNOWN | NET-01 |

| ID | Counterexample to attempt / mandatory RED test | Acceptance condition |
|---|---|---|
| `NET-01` | Trickled headers/body, early EOF, conflicting length, media range fuzz under small MAX_CONNECTIONS | Bound wall-clock and connection slots, correct status class, zero partial commits |
| `NET-02` | Spoof XFF/XFP from untrusted peer; spoof chain and IPv6 identities | No quota bypass/false HSTS with untrusted headers; actual edge evidence separate |
| `NET-03` | Hostile redirects, private-IP targets, DNS rebinding, non-TLS and credentials in URL | No signed lead crosses unapproved destination; synthetic tests isolate external network |
| `NET-04` | Synthetic 2xx before durable receiver acknowledgment; 408/429/5xx and timeout | No accepted lead lost; retries bounded; all ACK claims tied to external receipt ID |
| `NET-05` | 25k identities, IPv6 /64 churn, wall jumps, two independently spawned servers | No unbounded memory nor quota bypass within declared topology; unsupported topology fail closed |
| `NET-06` | Inject malformed href, quotes, svg/javascript schemes via fake public config | All payloads inert, console signals captured, CSP intact, negative mutation kills regression |
| `NET-07` | Inject XSS/SSRF-like sink, scanner crash, omitted requirement, altered wheel hash | Findings and gaps machine reported; waiver requires owner rationale; no full ASVS certification claim |
| `NET-08` | Attempt to read files outside sandbox, exhaust tasks/memory, abuse writable root | Resource caps and file/network boundaries proven, no break of media/API/backup |

### W3 — Product, accessibility, visual and commercial

| ID | Title | Priority | Current execution / evidence | Depends on |
|---|---|---|---|---|
| `WEB-01` | Manual + automated WCAG matrix across both themes | P1 | BLOCKED / UNKNOWN | EVD-04 |
| `WEB-02` | Independent full lab CWV repeatability | P1 | IMPLEMENTED / INFERRED | EVD-04 |
| `WEB-03` | Field INP/CWV with privacy-respecting RUM or CrUX | P1 | BLOCKED / UNKNOWN | WEB-02 |
| `WEB-04` | Theme switch stability, contrast under dynamic media | P2 | IMPLEMENTED / INFERRED | WEB-01, WEB-02 |
| `WEB-05` | Critical media and network budget as a regression contract | P2 | IMPLEMENTED / INFERRED | WEB-02 |
| `WEB-06` | Canonical metadata, SEO indexability, authoritative FQDN | P2 | BLOCKED / UNKNOWN | OPS-07 |
| `WEB-07` | Business/contact and tariff single-source consistency | P1 | BLOCKED / UNKNOWN | EVD-03 |
| `WEB-08` | Media licensing/provenance and true-claim inventory | P1 | BLOCKED / UNKNOWN | EVD-01 |

| ID | Counterexample to attempt / mandatory RED test | Acceptance condition |
|---|---|---|
| `WEB-01` | Focus traps, enlarged text 200%, empty labels, error states, modal mode | No critical WCAG A/AA finding; manual evidence named; axe alone never claimed complete |
| `WEB-02` | Force slow LCP or late shift while internally consistent summary says PASS | Independent budget violation rejects; field INP remains unknown |
| `WEB-03` | Inject long input tasks into critical user flow | Measured p75 by mobile/desktop meets owner-approved objectives or release HOLD |
| `WEB-04` | Load font after 500ms, dark/bright sampled frames, extreme landscape viewport | Any unprompted shift/contrast violation rejected at measured state with raw screenshots |
| `WEB-05` | Add unexpected high-priority video/font preload or corrupt poster | Per-profile transfer budgets from measured baseline; no broken poster or blank hero |
| `WEB-06` | Change canonical, og image or JSON-LD to mismatched domain | Canonical/schema/OG agree with owner-approved DNS+TLS; search indexing cannot be asserted absent field proof |
| `WEB-07` | Make JCB rate or VAT differ across JSON/JS/HTML while math still passes | No unapproved published rate or hidden VAT semantics; arithmetic independent oracle passes |
| `WEB-08` | Remove permission record for one video while bytes/hash remain valid | Every release asset has matched source rights and owner authorization; unresolved rights block publication |

### W4 — Operational SRE, business/legal release

| ID | Title | Priority | Current execution / evidence | Depends on |
|---|---|---|---|---|
| `OPS-01` | Separate liveness, readiness, delivery and business acceptance | P1 | IMPLEMENTED / INFERRED | NET-04 |
| `OPS-02` | Predeclare production SLI/SLO/alert thresholds | P1 | BLOCKED / UNKNOWN | OPS-01, WEB-03 |
| `OPS-03` | Correlate host, power-guard and external monitoring failures | P1 | IMPLEMENTED / INFERRED | OPS-01 |
| `OPS-04` | Authorize actual privacy processing and notices | P1 | BLOCKED / UNKNOWN | EVD-01 |
| `OPS-05` | Retention, deletion and backup lifecycle consistency | P1 | BLOCKED / UNKNOWN | DB-08, OPS-04 |
| `OPS-06` | Commercial effective-dated rates and quote semantics | P1 | BLOCKED / UNKNOWN | WEB-07 |
| `OPS-07` | Domain TLS edge, production rollout and rollback rehearsal | P1 | BLOCKED / UNKNOWN | NET-02, EVD-08 |
| `OPS-08` | Conjunctive owner release acceptance B1–B9 + T1–T7 | P1 | BLOCKED / UNKNOWN | EVD-08, OPS-02, OPS-04, OPS-05, OPS-06, OPS-07, WEB-08 |

| ID | Counterexample to attempt / mandatory RED test | Acceptance condition |
|---|---|---|
| `OPS-01` | Worker heartbeat fresh with 100 stale pending jobs and no receiver ACK | No metric implies greater assurance than observed; unknown/failed channel blocks release |
| `OPS-02` | Report 100% availability from synthetic soak with no field requests | Adopted pre-run SLO; no backfilled goals; actual monitored values with data-quality bounds |
| `OPS-03` | Trigger false heartbeat DOWN during intentional power guard; real failed sender | Each incident has provider event ID and root-cause status; unknown remains unknown |
| `OPS-04` | Find contact form with no approved policy and no documented retention authorization | Signed/recorded policy edition and purpose/retention decision or legal HOLD |
| `OPS-05` | Insert expired and legal-hold records, simulate deletion and restoration from old backup | Data lifecycle verified; no irreversible auto-delete without approved policy |
| `OPS-06` | Compare 1C external proposed rates with site, inject conflicting quote or rounding | Unknown or conflicting rate => publish HOLD or label explicitly unverified; no unapproved assumptions |
| `OPS-07` | Certificate mismatch, wrong DNS target, missing redirect/HSTS, broken new rollout | DNS/TLS/rollback proof and owner authorization separate from source CI |
| `OPS-08` | Keep one source absent and run green CI | Release PASS iff all mandatory leaves are evidence-verified at target version and owner deploy authorization exists |

### W5 — Adversarial and independent closure

| ID | Title | Priority | Current execution / evidence | Depends on |
|---|---|---|---|---|
| `ADV-01` | Threat model with attack trees and known trust boundaries | P1 | IMPLEMENTED / INFERRED | NET-03, NET-06 |
| `ADV-02` | Mutation score on critical safety and integrity contracts | P1 | IMPLEMENTED / INFERRED | EVD-03, EVD-04, DB-04 |
| `ADV-03` | Model/state-machine cross-process and temporal fault test | P1 | IMPLEMENTED / INFERRED | DB-03, NET-05 |
| `ADV-04` | Extended measured soak with anti-leak and adversarial events | P2 | IMPLEMENTED / INFERRED | EVD-05, OPS-01 |
| `ADV-05` | Date/locale/DST, integer precision, and boundary fuzz | P2 | IMPLEMENTED / INFERRED | WEB-07 |
| `ADV-06` | Supply-chain attestations and sandbox anti-tamper | P2 | IMPLEMENTED / INFERRED | NET-07, NET-08 |
| `ADV-07` | Real-device accessibility and UI adversarial evaluation | P2 | BLOCKED / UNKNOWN | WEB-01, WEB-03, WEB-04 |
| `ADV-08` | Final assurance case with signed release/no-release decision | P1 | BLOCKED / UNKNOWN | OPS-08, ADV-01, ADV-02, ADV-04, ADV-06, ADV-07 |

| ID | Counterexample to attempt / mandatory RED test | Acceptance condition |
|---|---|---|
| `ADV-01` | New data flow bypasses source-sink inventory without requiring update | Every high-impact path linked to at least one test and owner of risk |
| `ADV-02` | Mutate HMAC verification, FK checks, dedup uniqueness, replay or budget bounds | All designated critical mutants killed; score measured without arbitrary blanket 100% claim |
| `ADV-03` | Schedule concurrent retry, quota, crash and worker states with fake time | Minimal counterexample recorded; no lost accepted lead or silent invariant breach |
| `ADV-04` | Inject stuck downstream, server restart, disk pressure, repeated packet faults | Observed duration, integrity, backlog and process samples pass independent checker at same SHA |
| `ADV-05` | Time-zone offset around DST/day boundary, malformed Unicode and huge integer | All documented boundary cases invariant or explicit rejection; discrepancies fixed or scoped |
| `ADV-06` | Change action pin or wheel hash and replay stale receipt | Mutation rejected; valid source/runner/dependency manifest reproducible within documented limits |
| `ADV-07` | 200% text, high contrast, reduced motion, keyboard only, screen reader, iOS Safari | No unresolved WCAG AA critical failure and recorded field boundary; owner visual approval separate |
| `ADV-08` | Withdraw one mandatory provider receipt after all code gates become green | Zero mandatory unknowns, no new P0/P1, current immutable code proof, owner authorization; otherwise HOLD |

## Full 13-gate acceptance contract

| Gate | Type | Initial source state | Criterion |
|---|---|---|---|
| `G00` immutable_source | engineering | NOT_EXECUTED | source/ref/tree/runner immutable bindings |
| `G01` functional | engineering | NOT_EXECUTED | make gate and required test IDs |
| `G02` transport | engineering | NOT_EXECUTED | HTTP/HMAC/retry/timeout invariants |
| `G03` data | engineering | NOT_EXECUTED | FK, lead atomicity, idempotent commit |
| `G04` soak | engineering | NOT_EXECUTED | >=1800s raw synthetic resources and fault samples |
| `G05` security | engineering | NOT_EXECUTED | scoped and broad assessed security evidence |
| `G06` visual | engineering | NOT_EXECUTED | dual-theme 6-viewports, 32 PNG, axe + manual |
| `G07` proof_integrity | engineering | NOT_EXECUTED | source bound independent artifact verification |
| `G08` disaster_recovery | external | BLOCKED_EXTERNAL | offsite provider receipt plus independent restore/RPO/RTO |
| `G09` external_delivery | external | BLOCKED_EXTERNAL | real authenticated receiver ACK and configuration |
| `G10` business_privacy_rights | external | BLOCKED_EXTERNAL | approved prices/VAT, privacy, rights, contact/domain facts |
| `G11` field_experience | external | BLOCKED_EXTERNAL | field CWV including INP, real-device accessibility |
| `G12` release_control | external | BLOCKED_EXTERNAL | approved domain TLS, rollback and deployment authorization |

## Owner decisions B1–B9 (cannot be fabricated by agents)

| ID | Fact | Decision state | Evidence available |
|---|---|---|---|
| `B1` | Approved current itemized tariffs | NOT_AUTHORIZED | NOT PROVIDED |
| `B2` | VAT and minimum shift/idle/crane policy | NOT_AUTHORIZED | NOT PROVIDED |
| `B3` | Live lead delivery channel | NOT_AUTHORIZED | NOT PROVIDED |
| `B4` | Domain/DNS/TLS | NOT_AUTHORIZED | NOT PROVIDED |
| `B5` | TikTok media use | NOT_AUTHORIZED | NOT PROVIDED |
| `B6` | Authorship and footage origin | NOT_AUTHORIZED | NOT PROVIDED |
| `B7` | Privacy retention/lawful basis | NOT_AUTHORIZED | NOT PROVIDED |
| `B8` | Public email/Telegram contacts | NOT_AUTHORIZED | NOT PROVIDED |
| `B9` | Wikimedia attribution/brand approval | NOT_AUTHORIZED | NOT PROVIDED |

## Historic risks R01–R24 — revalidate against current HEAD

Historical `evidence_status` is NOT a fresh current-head verdict. Post-source mitigations exist for R01, R02, R06, R07, R08 and R19. Do not reopen any risk without a reproducible counterexample at the target SHA.

| ID | Baseline level/class | Historical finding | Task links |
|---|---|---|---|
| `R01` | P2 / CODE_CONFIRMED | SQLite foreign keys not enforced by db() | DB-01, DB-02 |
| `R02` | P1 / CODE_CONFIRMED | Restore filesystem cutover can be interrupted | DB-06, DB-08, ADV-08 |
| `R03` | P1 / EXTERNAL_UNVERIFIED | Off-device restore and RPO/RTO unproven | DB-07, DB-08, OPS-08, ADV-08 |
| `R04` | P1 / EXTERNAL_UNVERIFIED | Live receiver acknowledgment unverified | NET-04, OPS-01, OPS-02, DB-04, OPS-08, ADV-08 |
| `R05` | P1 / CODE_CONFIRMED | Readiness conflates local DB/disk health with service delivery | OPS-01, OPS-02, OPS-03 |
| `R06` | P1 / CODE_CONFIRMED | Evidence verifier hard-coded to historic PR8 | EVD-02, EVD-05, EVD-08, EVD-03, EVD-06, ADV-02 |
| `R07` | P2 / CODE_CONFIRMED | Independent mobile verifier omits threshold oracle | EVD-04, WEB-02, ADV-02 |
| `R08` | P2 / CODE_CONFIRMED | Browser idempotency lost after full reload | DB-05, NET-04, DB-03, DB-04 |
| `R09` | P1 / EXTERNAL_UNVERIFIED | Privacy policy and retention authorization missing | OPS-04, OPS-05, OPS-08, ADV-08 |
| `R10` | P1 / EXTERNAL_UNVERIFIED | Pricing/VAT and dispatch policy lacks approved current SSOT | OPS-06, WEB-07, OPS-08, ADV-05, ADV-08 |
| `R11` | P1 / EXTERNAL_UNVERIFIED | Media licensing and provenance not owner-authorized | WEB-08, OPS-08, ADV-08 |
| `R12` | P1 / EXTERNAL_UNVERIFIED | Domain and live edge/TLS unverified | OPS-07, NET-02, WEB-06, OPS-08, ADV-08 |
| `R13` | P2 / EXTERNAL_UNVERIFIED | Real-user mobile INP/CWV absent | WEB-02, WEB-03, OPS-02, EVD-04, WEB-05, OPS-08, ADV-05, ADV-07 |
| `R14` | P2 / SCOPE_LIMIT_CONFIRMED | Scoped AST scan cannot substitute broad SAST/DAST | NET-07, ADV-01, ADV-02 |
| `R15` | P2 / CONDITIONAL | DOM string composition and configuration URL trust surfaces | NET-06, ADV-01, NET-03 |
| `R16` | P2 / CODE_CONFIRMED | Process sandbox protection incomplete | NET-08, ADV-06 |
| `R17` | P2 / CONDITIONAL | Rate limits in memory depend on single-process topology | NET-05, ADV-03 |
| `R18` | P2 / CODE_CONFIRMED | SEO identity is not fully tied to confirmed production FQDN | WEB-06, WEB-07 |
| `R19` | P1 / CI_STATE_CONFIRMED | Main soak evidence absent for latest main at audit time | EVD-01, EVD-05, EVD-08, ADV-04 |
| `R20` | P2 / CONDITIONAL | Source/header parsing and reverse-proxy chain depend on deployment truth | NET-01, NET-02, ADV-03, NET-03, ADV-01 |
| `R21` | P2 / EXTERNAL_UNVERIFIED | Field visual accessibility cannot be certified with axe alone | WEB-01, WEB-04, ADV-07 |
| `R22` | P2 / SCOPE_LIMIT_CONFIRMED | Security supply chain lacks comprehensive source/build provenance | NET-07, ADV-06, EVD-07 |
| `R23` | P1 / EXTERNAL_UNVERIFIED | Outbox retry, crash and queue alerts require production SLO | OPS-01, OPS-02, OPS-03 |
| `R24` | P2 / EXTERNAL_UNVERIFIED | Operational monitoring has uncorrelated failures | OPS-03, ADV-04 |

## 20 cross-cutting audit actions

These are acceptance/operational work packages, not new product features or 20 proven vulnerabilities. The full evidence and acceptance conditions are in `00_AUDIT_ACT.md` (section C):

A-01 evidence reconciliation; A-02 branch admission enforcement; A-03 live receiver proof; A-04 current prices/VAT; A-05 privacy/retention; A-06 media rights; A-07 offsite DR; A-08 documentation drift; A-09 owner evidence signing; A-10 ZIP/JUnit/PNG raw verification; A-11 media source reproducibility; A-12 field CWV; A-13 manual accessibility; A-14 SEO/FQDN; A-15 video budgets; A-16 broad security provenance; A-17 production host sandbox; A-18 release/SLO/rollback; A-19 DOM trust retest; A-20 formal change scope.

## Invariant acceptance

- `ENGINEERING_ACCEPTED` only after external, authenticated Actions artifact bytes are retrieved, independently hashed/parsed, required JUnit IDs satisfied, critical mutants killed, all mandatory engineering claim leaves PASS for immutable SHA.
- `PRODUCTION_ELIGIBLE` additionally requires appropriately authorized B1–B9, R1–R3, H1, F1, S1, D1 receipts and host/field observations; schema-valid and workflows-green are insufficient.
- All output proofs state `source_sha`, exact GitHub event/run/attempt/job, provenance, raw samples, tool versions, and explicit null/unknowns.
- Do not alter normative baseline or weaker thresholds to get green, and do not commit credentials, personal-data samples or a production decision.

## Canonical references

- `assurance/source/tasks.json`; `assurance/source/gates.json`; `assurance/source/risks.json`; `assurance/source/owner_decisions.json`.
- `assurance/ledger.json`; `assurance/case.json`; `config/evidence-policy.json`; `config/required-tests.json`; `config/mutation-catalog.json`.
- `00_AUDIT_ACT.md`, `02_EXECUTION_AND_ACCEPTANCE.md`, `03_AGENT_PROMPTS.md`, `04_PRIMARY_SOURCES.md`.