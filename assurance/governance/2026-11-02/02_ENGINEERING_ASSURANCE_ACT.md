# PBT · Engineering Assurance Act / immutable source only

**Document type:** source-scoped engineering act (not an owner signature, production inspection, deployment receipt, or legal certificate).

- Repository: `neuron7x/pbt-site` (private)
- Audited Git revision: `main@dd85775749e28cf35c2e0c80c188b5dfbda21add`; original commit tree `d2044164e10501e8f9e069308725b73d88b274a3`
- Governance controller: [#15](https://github.com/neuron7x/pbt-site/issues/15), master audit backlog [#21](https://github.com/neuron7x/pbt-site/issues/21), runtime risk [#6](https://github.com/neuron7x/pbt-site/issues/6)
- Relevant merged change: [PR #27](https://github.com/neuron7x/pbt-site/pull/27), evidence collector EVD-06 provider rerun barrier
- Current separate GPT-owned evidence index: [Draft PR #28](https://github.com/neuron7x/pbt-site/pull/28) (not yet merged at document creation)
- Prior historical dossier: [Draft PR #22](https://github.com/neuron7x/pbt-site/pull/22); its `382a476b...` base is historical, not the current main

## A. Verified GitHub-native workflow execution at EXACT source SHA

The GitHub connector re-fetched jobs for all six **`push(main)`** runs; all applicable jobs report `completed/success`, with one designed PR-only step `skipped`:

| Gate | Run ID | Source of claim |
|---|---|---|
| Quality / release / mutation / meta | [41519202147](https://github.com/neuron7x/pbt-site/actions/runs/41519202147) | Authenticated jobs; required reports in source-scoped archive |
| HTTP / CRM HMAC / idempotency | [41519202274](https://github.com/neuron7x/pbt-site/actions/runs/41519202274) | Authenticated jobs |
| Visual, both themes | [41519202068](https://github.com/neuron7x/pbt-site/actions/runs/41519202068) | Authenticated jobs |
| Security / SBOM / scoped checks | [41519202139](https://github.com/neuron7x/pbt-site/actions/runs/41519202139) | Authenticated jobs |
| Measured synthetic ≥1800 s soak | [41519202063](https://github.com/neuron7x/pbt-site/actions/runs/41519202063) | Authenticated jobs; NOT production traffic |
| Read-only canonical reconciliation | [41519202095](https://github.com/neuron7x/pbt-site/actions/runs/41519202095) | Native closure workflow, no persisted norm ledger mutation |

**Previously independent original-byte evidence**, registered in [#15 checkpoint 6588729338](https://github.com/neuron7x/pbt-site/issues/15#issuecomment-6588729338) and indexed by PR #28 (reference to prior verification, **not a second ZIP-byte audit performed by writing this act**): 11/11 original provider ZIPs SHA-256 and ZIP CRC; 976 distinct release JUnit, 271 HTTP, 87 meta; 68 KILLED / 1 physical-power-loss UNTESTABLE / 0 SURVIVED; 32 PNG, 2921 PNG chunk CRC; synthetic soak 1800.045 seconds, 3999 accepted/delivered, 133 idempotent replays, raw p99 7.069 ms. Full canonical receipts remain in time-limited provider evidence until separately persisted byte-for-byte.

## B. Result classifications

| Dimension | Classification | Evidence / boundary |
|---|---|---|
| Exact-source GitHub jobs | **VERIFIED via authenticated jobs** | Six run IDs above |
| Independent ZIP/JUnit/PNG/soak at source SHA | **PRIOR EVIDENCE**, not newly re-executed here | #15 and PR #28 index; check raw provider bytes again for new commit |
| Source-scoped closure C1–C9 | **ENGINEERING_ACCEPTED_LOCAL_PROOF_ONLY** for `dd85775749e28cf35c2e0c80c188b5dfbda21add` | Read-only closure report previously recorded in #15 |
| 30 engineering obligations | **Prior source-scoped VERIFIED** | Normative `ledger.json` still says `IMPLEMENTED/INFERRED`; not overwritten |
| 18 external obligations | **BLOCKED_EXTERNAL / UNKNOWN** | No authenticated owner/host/field receipts |
| C0/C10 / production approval | **UNKNOWN / HOLD** | Not self-authorized by CI |
| Draft PR #28 and this dossier | **UNKNOWN until exact PR HEAD gates finish** | Previous `main` receipts cannot be transplanted |

## C. Explicit negative findings / limits

No actual CRM receiver acknowledgement, production TLS/DNS attestation, external offsite restore/RPO/RTO, owner-approved pricing/VAT, privacy or copyright consent, field CWV/INP, two-theme manual WCAG-EM sign-off, or production release instruction is established by this act. Successful synthetic HMAC/ACK testing does not prove real receiver ACK. Systemd/host permissions require actual approved host. GitHub `main` was historically observed without enforceable protection; a reported green run is not a platform-enforced admission policy. Re-evaluate current repository policy separately.

**Decision: SOURCE-SCOPED ENGINEERING PROOF AT dd85775749e28cf35c2e0c80c188b5dfbda21add; PRODUCTION HOLD.** The act is a factual record, never a replacement for original ZIP bytes, canonical receipts, owner-signed evidence or a future-SHA release decision.
