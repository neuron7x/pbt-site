# PBT · Prioritized Execution Board (no duplicate controllers)

**Baseline:** `dd85775749e28cf35c2e0c80c188b5dfbda21add`; controller [#15](https://github.com/neuron7x/pbt-site/issues/15), work backlog [#21](https://github.com/neuron7x/pbt-site/issues/21). These checkboxes describe future execution, not completed actions; check only after exact-HEAD proof.

## Parallel, file-disjoint engineering tracks

- [ ] **TRACK-EVD-PERSIST / P1** — finish [Draft PR #28](https://github.com/neuron7x/pbt-site/pull/28) after original quality/release JUnit and >=1800 s soak evidence; if full CI + provider bytes PASS, guarded merge. Then independently verify all **new** exact-main runs and 9 mandatory artifact roles. Owner: GPT evidence branch, `assurance/evidence/**` only. No normative ledger self-promotion.
- [ ] **TRACK-EVD-RECEIPTS / P1** — from authenticated, exact-main closure ZIP, preserve actual full `receipts.json`, `reconciled-ledger.json`, `reconciled-case.json` and `SHA256SUMS` in a separate narrowly scoped evidence-only PR; independently verify canonical bytes and digest. Never transform historical dd857 receipt into a later HEAD acceptance. Owner: separate GPT evidence-only branch after stabilization.
- [ ] **TRACK-DOCS / P2** — reconcile [Draft PR #22](https://github.com/neuron7x/pbt-site/pull/22) as a dated **historical** `382a476b...` audit, review for correctness and possible archive-only merge using **new exact PR-head** quality/soak; do not rewrite into fake current evidence. Owner: audit branch; this dossier avoids `docs/audit/**`.
- [ ] **TRACK-BRANCH-PROTECTION / P1** — owner to establish actual enforceable private repository branch rules or record explicit platform/plan block; audit bypass possibility. Do not make the repository public to buy features.
- [ ] **TRACK-SOURCE-REGRESSION / P1** — only on verified RED at current HEAD, isolate SQL crash/legacy FK, lost-response idempotency, ACK truthfulness, EVD-06 provider rerun drift and mandatory test identity mutations; preserve CRM/HMAC contracts. Owner: single GPT-owned narrow source PR, no Opus path collision.

## Independent owner/field lanes (cannot be auto-completed)

- [ ] **T1 / commercial:** B1/B2 approved tariff/VAT/shift and effective date, independent quote consistency.
- [ ] **T2 / receiver:** B3/B8 real CRM/webhook/Telegram ACK receipt with non-PII correlation, live secret-safe config evidence.
- [ ] **T3 / edge:** B4 actual DNS/TLS/redirect, proxy trust and explicit deployment authorization.
- [ ] **T4 / rights:** B5/B6/B9 valid permissions for all images/video and attributable stock.
- [ ] **T5 / legal:** B7 privacy policy, data retention, historical logs, deletion/backup drill.
- [ ] **T6 / DR:** offsite encrypted backup provider receipt, separate-host restore, RPO/RTO and watermarks.
- [ ] **T7 / release:** actual devices, manual WCAG review, field INP/CWV, actual SLI/SLO, alerts and release/rollback decision.

**Hard stop:** any `UNKNOWN` mandated source/production proof; source drift, failed or pending applicable CI, unverified artifact bytes or unapproved owner decision. No deploy or live CRM changes.
