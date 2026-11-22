# PBT Site — External Evidence Intake and Production HOLD Act

**Target SHA:** `382a476b3803f03a8dd1de53c69931f551719151`. **Decision:** PRODUCTION HOLD. This file projects all 16 actual classes in `config/external-evidence-policy.json`, without manufacturing a release.

**Trust boundary:** An agent may validate an existing owner's fact but may not create a business fact, legal judgment, owner identity key, live customer record, TLS certificate or signed authorization. `config/owner-allowed-signers` is empty by design.

## Complete 16-class policy projection

| Class | Authority and fact | Required receipt fields | Task links | Claim leaf | Expires |
|---|---|---|---|---|---|
| `B1` | Approved effective-dated tariffs — owner | `subject`, `effective_from`, `document_sha256` | OPS-06, WEB-07 | `C10.prices_vat` | no |
| `B2` | VAT, minimum shift, idle, crane and dispatch policy — owner | `subject`, `effective_from`, `document_sha256` | OPS-06, WEB-07 | `C10.prices_vat` | no |
| `B3` | Live delivery channel and receiver receipt naming real lead ids — owner on receiver records | `subject`, `receipt_id`, `persisted_lead_ids` | NET-04 | `C10.live_delivery` | no |
| `B4` | Domain, DNS, HTTPS and trusted proxy chain — owner plus independent DNS/TLS check | `subject`, `fqdn`, `certificate_sha256` | NET-02, OPS-07, WEB-06 | `C10.edge` | yes |
| `B5` | Rights to customer footage — owner | `subject`, `document_sha256` | WEB-08 | `C10.media_rights` | no |
| `B6` | Authorship and origin of frames — owner | `subject`, `document_sha256` | WEB-08 | `C10.media_rights` | no |
| `B7` | Privacy purpose, notice, lawful basis and retention — owner and lawyer | `subject`, `effective_from`, `document_sha256`, `retention_days` | OPS-04, OPS-05 | `C10.privacy` | no |
| `B8` | Public communication channels — owner | `subject`, `document_sha256` | WEB-06 | `C10.edge` | no |
| `B9` | Illustration consent and attribution form — owner | `subject`, `document_sha256` | WEB-08 | `C10.media_rights` | no |
| `R1` | Off-device encrypted snapshot — storage provider receipt, endorsed by owner | `subject`, `provider_receipt_id`, `snapshot_sha256` | DB-07 | `C10.off_device_restore` | yes |
| `R2` | Separate-host restore with RPO/RTO adopted before the run — operator, endorsed by owner | `subject`, `host_identity`, `rpo_policy`, `rto_policy`, `measured_rto_s`, `rpo_gap_ids`, `snapshot_sha256` | DB-08 | `C10.off_device_restore` | yes |
| `R3` | Isolation measured on the actual production target — operator on target | `subject`, `host_identity`, `probe_output_sha256` | NET-08 | `C10.sandbox` | yes |
| `H1` | Named human accessibility evaluation with assistive technology and real devices — named evaluator, endorsed by owner | `subject`, `evaluator`, `matrix_sha256` | WEB-01, ADV-07 | `C10.accessibility_human` | yes |
| `F1` | Field performance, or an authorized bounded pilot — field data provider, endorsed by owner | `subject`, `sample_size`, `window`, `dataset_sha256` | WEB-03 | `C10.field_inp` | yes |
| `S1` | SLO adopted before measuring — owner | `subject`, `effective_from`, `document_sha256` | OPS-02, OPS-05 | `C10.field_inp` | no |
| `D1` | Explicit release authorization for the exact revision — owner | `subject`, `release_sha` | OPS-07, OPS-08, ADV-08 | `C10.authorization` | yes |

## External receipt admission protocol

1. An actual authorized owner or operator supplies the factual original **outside public issues and CI**. Record its document digest after redacting sensitive contact/secret content.
2. Validate origin, subject, time and expiry, all required fields and cross-consistency with the current intended target revision.
3. Validate a detached SSH signature against the owner-administered signer allowlist. An agent never creates a signer or self-signs as the owner.
4. Store approved non-sensitive receipts only in the policy-defined evidence folder; no credentials, real lead contact payloads, production databases or raw logs.
5. Independently confirm the underlying assertion: tariffs against approved source; B3 against receiver-persisted IDs; B4 against DNS/TLS; media rights per original; B7 against legal/owner policy; R1/R2 off-host restore with watermark; R3 actual system unit sandbox; H1 device/assistive tech; F1 field dataset; S1 adopted SLO; D1 exact SHA.
6. Expired, unverifiable, missing or self-issued material remains UNKNOWN/BLOCKED_EXTERNAL.
7. `tools/assurance_check.py --require production` must fail or HOLD until genuine engineering and external acceptance. Never override a refusal.

## Minimal owner-facing requests

| Topic | What is needed | Consequence of missing proof |
|---|---|---|
| B1/B2 tariffs | Dated itemized approved source; VAT, idle, minimum shift and dispatch/crane rules | Pricing and quote publication HOLD |
| B3/B8 channels | Approved real receiver and contacts; non-PII persisted IDs, secret-safe HMAC/TLS | Live lead delivery UNKNOWN |
| B4/D1 deployment | FQDN, DNS, TLS proxy, explicit exact-SHA owner authorization | Deployment HOLD |
| B5/B6/B9 footage | Per-asset client origin, rights or permitted license and attribution | Media release HOLD |
| B7 privacy | Lawful basis, transparent notice, approved retention/deletion and historical backup/log lifecycle | PII production acceptance HOLD |
| R1/R2/R3 resilience | External storage, independent restore policy and measured RPO/RTO, host least privilege | Recovery claims UNKNOWN |
| H1/F1/S1 performance | Real devices/assistive tech, field p75 CWV and approved SLO | Field accessibility and SRE UNKNOWN |

## Anti-fraud and limitations

- Signature proves identity and integrity of a **claim**, not truth of a tariff or a legal permission. Cross-check first-party records.
- A successful synthetic CRM, GitHub CI, isolated backup or media SHA does not replace external receipt.
- A Playwright WebKit emulation is not an actual iPhone; field INP cannot be inferred from lab LCP/CLS.
- Under Ukrainian law 2297-VI article 6, contact records require purpose-limited processing/retention; the lawful basis and actual period require a context-specific owner/legal decision.

Sources: `config/external-evidence-policy.json`; `tools/external_receipts.py`; `docs/PRODUCTION_HOLD.md`; https://zakon.rada.gov.ua/laws/show/2297-17.
