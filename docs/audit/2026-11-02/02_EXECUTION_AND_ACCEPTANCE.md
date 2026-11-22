# PBT Site — Canonical Execution, Falsification and Acceptance Protocol

**Revision under audit:** `382a476b3803f03a8dd1de53c69931f551719151` (2026-11-02).
**Control surfaces:** `assurance/source/tasks.json` (W0–W5), `assurance/ledger.json`, `assurance/case.json`, issue #4, issue #6, issue #15. This protocol adds no new business scope and does not authorize production.

## I. First principles and epistemic constraints

1. **Source code is a hypothesis.** A function, test or claim marked IMPLEMENTED is not proven until its observable behavior survived the declared oracle and adversarial controls.
2. **Evidence is immutable and revision-bound.** All run results carry original `repo`, complete `source_sha`, actual checkout SHA, event, run ID/attempt, environment/toolchain, raw artifacts and independently checked digests.
3. **Evidence is conjunctive.** All mandatory gates pass; missing/unknown is HOLD. A score, number of tests or a green badge cannot offset one critical loss-of-lead flaw.
4. **Separate scopes.** Software engineering acceptance != signed customer facts != field measurement != production deployment.
5. **Negative tests first.** Each defect needs a reproducible counterexample, a failing test on the old state, minimal fix, green oracle, mutation/negative control, then whole-run regression.
6. **No artificial completion.** Do not add magic numbers, falsify tariffs, construct synthetic production receipts, weaken budget thresholds, silently change requirements or remove a mandatory test.
7. **Isolation.** New code on a narrowly owned branch from freshly observed `main`; no direct main push, no force, no deletion, no overlap with issue #15 successor owner; PR draft until independently proven.
8. **Machine limitations.** Agent and GitHub connector cannot inspect physical devices, private CRM, real customers or unshared owner secrets. These stay UNKNOWN/BLOCKED, never guessed.

## II. Preflight and baselines — W0 / evidence closure first

Record from GitHub API: current main HEAD SHA, its commit/tree, all branch refs and open PRs, five workflow run IDs and all jobs, selected artifact IDs/provider digests, 48 source tasks, 24 historic risks, 29 claim-leaf states, independent owner receipts. Abort mutation if current main advanced during review.

Use a DISPOSABLE isolated worktree on a capable authorized development host (not the live service tree):

```bash
git fetch origin main
git worktree add --detach ../pbt-audit 382a476b3803f03a8dd1de53c69931f551719151
cd ../pbt-audit
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.txt
.venv/bin/python -m playwright install --with-deps chromium webkit
PY=.venv/bin/python make gate
PY=.venv/bin/python make mutation
PY=.venv/bin/python make assurance
```

`make assurance` without `--require` is SCHEMA_VALID ONLY. Never misstate this as an engineering acceptance. If original media sources are absent, do not attempt `make media`/`make stock` and call the inputs reproducible; request authorized, hash-pinned sources first.

**Exact-main proof capture and reconciliation** (on an authorized host with authenticated GitHub API access, using their documented CLI options):

```bash
python3 tools/evidence_collect.py --kind push --head 382a476b3803f03a8dd1de53c69931f551719151 --base "$(git rev-parse 382a476b^)" --out evidence/
python3 tools/meta_evidence_gate.py --help
python3 tools/evidence_reconcile.py --help
python3 tools/evidence_reconcile.py --evidence-dir evidence/ --close
python3 tools/assurance_check.py --require engineering --evidence-dir evidence/
```

Help/argument inspection is mandatory where CLI semantics may differ. The reconciler must be run on a disposable writable copy; do not automatically commit promoted artifacts. The offline verifier and reconciler must not be fed credentials or user contact data.

Negative falsification matrix for EVD-01..08 (each must produce a non-zero refusal): stale `source_sha`; wrong PR vs main event; mismatched artifact role; missing test identity with enough other tests; forged PASS label; above-budget p75 from raw samples; invalid PNG chunk/ZIP CRC; changed artifact digest; mutation survivor; forbidden output path; missing provider authentication binding. Record actual exit statuses and sealed original input hashes.

## III. Ordered work packets — re-run rather than rewrite implemented tasks

### W0 — acceptance/provenance (EVD-01..EVD-08)

First independently retrieve the **nine** exact-main artifact roles defined in `config/evidence-policy.json` (release, mobile, http, visual, osv, static, soak, mutation, sast). Verify original provider metadata plus actual ZIP bytes and role/source SHA; parse JUnit identities and counts, PNG CRC, raw synthetic LCP/CLS, mutation ledger and 1800-s soak samples. Only then promote ledger/case with reconciliation. If provider direct ZIP download is unavailable, stop at PROOF_HOLD; do not substitute connector text or historical PR proofs.

Exit: `python3 tools/assurance_check.py --require engineering --evidence-dir evidence/` exits 0 on exact head, with every required leaf PASS. Re-fetch main HEAD after deciding; drift -> HOLD.

### W1 — SQLite, idempotency, recovery (DB-01..DB-08)

Do not reimplement existing FK pragma, restore cutover, reload key or transaction work unless RED current-head behavior justifies it. Re-execute actual-process tests: FK orphan rejection on EVERY connection; legacy anomalous DB reporting without destructive repair; single durable logical lead for same idempotency key under concurrency and restart; different payload 409; 201 only after lead+outbox commit; SIGKILL at stated cutpoints; interrupted restore leaves old/new generation; no hot WAL/journal poisoning; ENOSPC/EIO. Record comparison of before/after DB and outbox IDs.

Separate `SIGKILL` (OS page cache preserved) from **power-loss, torn-sector, reordered-storage** model. A unit test using SIGKILL is not a power-loss proof. Offsite R1/R2 evidence needs actual encrypted independent provider plus separate-host restore and adopted RPO/RTO; this is owner/operator-gated.

### W2 — HTTP, security, trust boundaries (NET-01..NET-08)

Use RFC 9112 test matrix: conflicting/duplicate Content-Length, Content-Length+Transfer-Encoding, truncated body, valid/invalid chunking, absolute header/body deadline under adversarial trickle, unsupported media types, open connection exhaustion, abusive Host/X-Forwarded-For, Origin/CORS, idempotency races, cookie/storage boundaries, static file path canonicalization. Observe response + no leaked PII or persisted partial state. Test redirects and outbound HMAC credential forwarding, HTTPS-only for remote endpoints. Never send tests to an unauthorized public endpoint.

Use OWASP ASVS 5.0.0 and WSTG v4.2 with scoped control mapping. Pinned AST/OSV/SAST checks are necessary but **not proof of full ASVS, DAST, vulnerability absence or SLSA level**. Threat-model actual DOM sinks, URLs, and external trust; run controlled inert-string/XSS negatives for both themes.

### W3 — visual/UX/video/accessibility (WEB-01..WEB-08)

Test both `sky` and `precision` themes at the six defined viewports and responsive transitions. Test keyboard focus, dialog/menu close, forms/calculator, content order, 200%/400% zoom/reflow, safe theme persistence without FOUC, dark/bright scenes, long translated labels, low bandwidth, Save-Data, `prefers-reduced-motion`, autoplay policy, video poster fallback, visible text against real moving frames, pauses and absent JS.

Media chain: inventorize each of 26 distinct MP4 encodings and matching WebM/poster variations; classify which source clip is client footage vs Wikimedia, store link/license + SHA, encode parameters, LUT toolchain, generated frame size and rights receipt. Never infer rights or authenticity from a hash. Reconstruct authorized source material in fresh environment before calling the media build deterministic.

Performance: distinguish transfer budget (MB) from frame decode/render, first-content stability and actual perceived UX. Lab: cold/warm runs, multiple devices / browsers, fixed emulated network+CPU, per-theme p75 nearest-rank, video and still fallback. Google CWV good thresholds are LCP <=2.5s, INP <=200ms, CLS <=0.1 at field p75, segmented by device. **Synthetic INP cannot certify field INP**. Real visual acceptance requires independent observation of actual screenshots and source/finished browser render, not just PNG digest.

WCAG AA conformance cannot be inferred from `axe=0`. Follow W3C WCAG-EM 2.0 with sampled interactions and manual screen-reader / real devices; assess whether each video is decorative vs meaningful and whether text equivalent is required. Record each success criterion, tested state, browser, input method, finding, and remediation evidence.

SEO/FQDN: owner-approved domain is necessary to validate canonical URL, OpenGraph and JSON-LD identity, `robots.txt`, sitemap policy and search indexability. Do not replace with guessed domain or mark all SEO as verified from a local file.

### W4 — observability, privacy and release operations (OPS-01..OPS-08)

Separate: liveness (`/api/health` process/DB), readiness (outbox backlog/worker), transport 2xx, CRM persistence, downstream business acceptance. Define numerator, denominator and measurement window for each SLI. Have owner adopt SLO and error budget before evaluating against it (Google SRE). Set alerts for backlog age, terminal failures, retries, worker inactivity, backups and no-receipt uncertainty. Monitor cannot invent operator resolution.

Retention: personal contact lead rows need the owner's lawful purpose, notice, retention and deletion/backup expiry decisions. Test that deletion policy removes data at approved cutoff, preserves integrity/information required for financial/legal obligations, and does not leave stale backups/logs indefinitely. Do not purge without owner-approved policy and legal review.

Deployment: require target FQDN/TLS/proxy chain, least-privilege dedicated system identity, runtime sandbox measured on actual host, DNS/certificate facts, secret isolation, offsite backup and independent restore, approved rollback, documented incident path and signed exact SHA D1. No direct production mutation from an AI agent's unsupported guess.

### W5 — independent challenge and assurance closure (ADV-01..ADV-08)

Run threat model and mutation campaign (69 configured mutants; each verdict KILLED/SURVIVED/INVALID/UNTESTABLE preserved); seed random temporal/stateful traces across concurrency, crash, timezones, and transport failures. Run exact-head 1800+ s synthetic soak and verify raw latency/RSS/fault counters from actual source-matched bytes; do not infer 24/7 performance or a deployment SLO. Recompute C1..C10 evidence graph. C10 remains UNKNOWN until real external receipts.

## IV. T1–T7 operational overlay

| Track | Relevant tasks | Required owner/environment receipt | Release status until receipt |
|---|---|---|---|
| T1 pricing/VAT | WEB-07, OPS-06 | Effective-date price table, VAT + idle/crane policy | HOLD |
| T2 actual delivery | NET-04, OPS-01 | TLS/HMAC + receiver-persisted IDs; no lead PII in logs | HOLD |
| T3 domain/edge | NET-02, WEB-06, OPS-07 | Authorized FQDN, DNS, cert chain, proxy hop test | HOLD |
| T4 media rights | WEB-08 | Client footage ownership + per Wikimedia attribution | HOLD |
| T5 privacy/security | OPS-04, OPS-05, NET-07 | Lawyer/owner basis & retention; deletion/old-log treatment | HOLD |
| T6 disaster recovery | DB-07, DB-08 | External encrypted snapshot & independent restore / RPO-RTO | HOLD |
| T7 SRE/release | OPS-02, OPS-03, ADV-07, ADV-08 | Real-device/field SLI, rollback + exact-SHA D1 | HOLD |

## V. Evidence artifact and finding templates

### Finding object

```yaml
finding_id: PBT-<CATEGORY>-NN
target_sha: 382a476b3803f03a8dd1de53c69931f551719151
location: <path:line>
claim: <single falsifiable sentence>
epistemic_status: SOURCE_OBSERVED | EXPERIMENT_REPRODUCED | EXTERNAL_UNKNOWN
severity: P0 | P1 | P2 | P3
threat_or_failure_model: <bounded preconditions>
independent_primary_source: <versioned specification URL and applicable section>
counterexample: <exact executable input, environment, command>
observed_failure: <stdout/exit/JUnit/source digest>
oracle: <test path and expected vs actual>
minimal_remediation: <files/invariant to preserve>
negative_control: <mutation that must be rejected>
regression: <whole-gate evidence>
owner_of_decision: engineer | customer | host_operator | legal
closure: PASS | FAIL | BLOCKED | UNKNOWN
```

### Release decision object

```yaml
release_target_sha: <40 hex>
claims: {C1: UNKNOWN, C2: UNKNOWN, C3: UNKNOWN, C4: UNKNOWN, C5: UNKNOWN, C6: UNKNOWN, C7: UNKNOWN, C8: UNKNOWN, C9: UNKNOWN, C10: UNKNOWN}
provider_runs: <five exact-head IDs/attempts/jobs>
downloaded_artifacts: <nine roles, provider digests and verified bytes>
engineering_decision: ENGINEERING_ACCEPTED | PROOF_HOLD | EVIDENCE_REJECTED
production_decision: PRODUCTION_ELIGIBLE | PRODUCTION_HOLD
external_signatures: <only actual authorized receipts, else null>
deployment_authorization: <owner signed exact SHA or null>
```

## VI. Explicit STOP/FREEZE rules

- Open competing PR touching same source paths, source SHA drift, cancelled/in-progress required role, JUnit mandatory omission, arbitrary threshold change, missing raw ZIP bytes or mutation survivor => STOP and reconcile, do not merge.
- Evidence failure is not permission to erase a historical negative run. Preserve RED→GREEN and environment provenance.
- Unresolved owner tariff, VAT, live receiver, domain/TLS, media rights, privacy, offsite recovery, field testing or exact SHA authorization => NO PROD DEPLOY.
- No new human reviewer requirement for solo source engineering; named real-device/accessibility and external owner receipts remain separate observable work.
- New features (CMS, live fleet availability, accounts, payment, multi-page SEO) are explicitly OUT OF CURRENT SCOPE unless separately authorized.

## VII. Final acceptance checklist

- [ ] 48 task statuses derived from immutable source and latest raw evidence; no stale claims or duplicated historic risks.
- [ ] All five required exact-main workflows current and successful; nine source-bound provider artifact roles independently verified.
- [ ] Mandatory JUnit case IDs and zero forbidden skipped/xfail, threat mutants and browser screenshot proofs verified.
- [ ] All C1–C9 engineering leaves PASS at same compatible SHA; `--require engineering` returns 0.
- [ ] PBT marketing video and 2-theme UX have documented 6-viewport, reduced motion, WebKit and assistive-tech findings, not only code assertions.
- [ ] External B1–B9, R1–R3, H1/F1/S1/D1 facts have authorized provenance and are temporally valid, or production remains HOLD.
- [ ] Live lead receipt, offsite recovery, field SLIs, TLS, privacy, media rights and explicit owner deployment authorization observed.
- [ ] No secrets or lead PII in GitHub tickets, artifacts or commits; all changes on isolated PRs, source HEAD rechecked before release.

**Primary-source bibliography:** `04_PRIMARY_SOURCES.md`. **Delegated executor prompts:** `03_AGENT_PROMPTS.md`.