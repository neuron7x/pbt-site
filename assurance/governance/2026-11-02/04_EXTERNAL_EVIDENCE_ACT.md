# PBT · External Evidence & Owner Action Act

**Source SHA:** `dd85775749e28cf35c2e0c80c188b5dfbda21add` · **State:** 18 source obligations are `BLOCKED/UNKNOWN` in committed ledger. None is closed by this document; no actual owner signature, receipt, domain access or field observation has been supplied by this act. [Operational controller #6](https://github.com/neuron7x/pbt-site/issues/6), [owner blockers](../../../docs/RELEASE_STATUS.md), [audit external requirements](https://github.com/neuron7x/pbt-site/pull/22).

## 1. Mandatory receipt schema (minimum)

Every real record must have: `claim_id`, `source_sha` or actual deployed version, verified issuing organization/person and authorization, `observed_at_utc`, applicable service/entity, method and scope, immutable attachment SHA-256, independent cross-check or limitations, validity period, explicit owner decision where required. **No secrets, contact PII, unredacted CRM leads or cryptographic private keys in GitHub.** Redacted claim IDs must remain correlatable with approved secure external records. Empty/unsigned templates are NOT evidence.

## 2. Eighteen unresolved obligations (action queue)

| ID | Evidence owner | Missing real-world proof / acceptance | Status |
|---|---|---|---|
| **DB-07** | Owner + infrastructure operator | Provider receipt + offline restore verified against source snapshot; local-only copies not counted | `BLOCKED/UNKNOWN` |
| **DB-08** | Owner + infrastructure operator | No unreconciled known loss; actual RPO/RTO numbers and limitations recorded; owner adopts thresholds | `BLOCKED/UNKNOWN` |
| **NET-02** | Owner + infrastructure operator | No quota bypass/false HSTS with untrusted headers; actual edge evidence separate | `BLOCKED/UNKNOWN` |
| **NET-04** | CRM/receiver owner | No accepted lead lost; retries bounded; all ACK claims tied to external receipt ID | `BLOCKED/UNKNOWN` |
| **NET-08** | Owner + infrastructure operator | Resource caps and file/network boundaries proven, no break of media/API/backup | `BLOCKED/UNKNOWN` |
| **WEB-01** | Independent accessibility / real device evaluator | No critical WCAG A/AA finding; manual evidence named; axe alone never claimed complete | `BLOCKED/UNKNOWN` |
| **WEB-03** | Approved field/SRE operator | Measured p75 by mobile/desktop meets owner-approved objectives or release HOLD | `BLOCKED/UNKNOWN` |
| **WEB-06** | Domain/SEO owner | Canonical/schema/OG agree with owner-approved DNS+TLS; search indexing cannot be asserted absent field proof | `BLOCKED/UNKNOWN` |
| **WEB-07** | Commercial owner | No unapproved published rate or hidden VAT semantics; arithmetic independent oracle passes | `BLOCKED/UNKNOWN` |
| **WEB-08** | Media rights owner | Every release asset has matched source rights and owner authorization; unresolved rights block publication | `BLOCKED/UNKNOWN` |
| **OPS-02** | Approved field/SRE operator | Adopted pre-run SLO; no backfilled goals; actual monitored values with data-quality bounds | `BLOCKED/UNKNOWN` |
| **OPS-04** | Owner + privacy/legal | Signed/recorded policy edition and purpose/retention decision or legal HOLD | `BLOCKED/UNKNOWN` |
| **OPS-05** | Owner + privacy/legal | Data lifecycle verified; no irreversible auto-delete without approved policy | `BLOCKED/UNKNOWN` |
| **OPS-06** | Commercial owner | Unknown or conflicting rate => publish HOLD or label explicitly unverified; no unapproved assumptions | `BLOCKED/UNKNOWN` |
| **OPS-07** | Owner + infrastructure operator | DNS/TLS/rollback proof and owner authorization separate from source CI | `BLOCKED/UNKNOWN` |
| **OPS-08** | Authorized owner + independent verifier | Release PASS iff all mandatory leaves are evidence-verified at target version and owner deploy authorization exists | `BLOCKED/UNKNOWN` |
| **ADV-07** | Independent accessibility / real device evaluator | No unresolved WCAG AA critical failure and recorded field boundary; owner visual approval separate | `BLOCKED/UNKNOWN` |
| **ADV-08** | Authorized owner + independent verifier | Zero mandatory unknowns, no new P0/P1, current immutable code proof, owner authorization; otherwise HOLD | `BLOCKED/UNKNOWN` |

## 3. Business/operational B1–B9 (not implied by source engineering)

| Owner claim | Minimum authorized decision/receipt |
|---|---|
| B1 / B2 | Effective-dated rates, units, VAT inclusion/exclusion, minimum shift, idle, crane dispatch; reconcile source-of-truth conflicts without guessing |
| B3 / B8 | Approved real CRM/webhook/Telegram routing, trusted end-to-end receiver acknowledgment and real company contact data, redacted non-PII correlation |
| B4 | Owner-controlled FQDN and actual DNS/TLS/redirect/proxy attestation, separate deploy authorization |
| B5 / B6 / B9 | Per-asset original provenance, license/usage rights and company brand approval; do not infer rights from SHA or social media appearance |
| B7 | Approved purpose/consent-or-other-lawful-basis, privacy notice, retention, actual erasure process, backup/log lifecycle under applicable law |

Additional operator evidence: independent offsite encrypted backup + separate-host restore and measured RPO/RTO; real field CWV/INP/SLO and accessibility observations; production monitoring and rollback rehearsal; explicit exact-target deployment decision. The synthetic CI soak does not count.

**Decision:** 18 external obligations remain `BLOCKED_EXTERNAL`; `C0/C10=UNKNOWN`. These requests are to be fulfilled by authorized people/systems outside this connector, with independent authenticity verification and no automatic release.
