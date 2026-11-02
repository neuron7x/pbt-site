# PBT Site · Canonical Audit Dossier / 2026-11-02

**Live audit controller:** https://github.com/neuron7x/pbt-site/issues/21
**Base:** `neuron7x/pbt-site@382a476b3803f03a8dd1de53c69931f551719151`.
**Branch:** `audit/canonical-evidence-20261102` — documentation-only, not a production rollout.

## The seven signed-off-as-written documents (NOT engineering acceptance)

| Artifact | Content / purpose |
|---|---|
| [00_AUDIT_ACT.md](00_AUDIT_ACT.md) | Source and provider facts, 20 new cross-cutting actions, classified defects, limitations, current no-release decision |
| [01_TASK_REGISTER.md](01_TASK_REGISTER.md) | Exact 48 source obligations, 13 gates, nine owner decisions, 24 historical risk records, task-specific red tests and acceptance predicates |
| [02_EXECUTION_AND_ACCEPTANCE.md](02_EXECUTION_AND_ACCEPTANCE.md) | W0–W5 engineering protocol, T1–T7 owner overlay, falsification/reproduction/rollback/CI and release decision |
| [03_AGENT_PROMPTS.md](03_AGENT_PROMPTS.md) | Seven separate model operator roles and traceable checkpoint contract, output in English for machine use |
| [04_PRIMARY_SOURCES.md](04_PRIMARY_SOURCES.md) | Versioned standards and first-party bibliography, applied control/test mapping, stable vs draft distinction |
| [05_EXTERNAL_EVIDENCE_ACT.md](05_EXTERNAL_EVIDENCE_ACT.md) | All 16 B1–B9/R1–R3/H1/F1/S1/D1 external receipt classes and anti-forgery boundary |
| [06_PROVIDER_METADATA_SNAPSHOT.json](06_PROVIDER_METADATA_SNAPSHOT.json) | Recorded 5 exact-main Action success statuses and 10 artifact metadata objects (9 mandatory); NOT independent byte verification |

## Three distinct verdicts

1. **Source status**: 5/5 latest exact-head workflow executions report SUCCESS; 30 of 48 obligations IMPLEMENTED/INFERRED; 18 BLOCKED/UNKNOWN in ledger.
2. **Engineering acceptance**: 29/29 claim leaves UNKNOWN; independent ZIP/CRC/raw JUnit/soak byte re-verification not done in this audit. No `ENGINEERING_ACCEPTED` claim.
3. **Production readiness**: `PRODUCTION_HOLD`, owner data and actual deployment/field evidence outstanding. No deployment authorized.

## Authoritative precedence

1. Immutable released source at audited SHA and actual independent experiment/receipt.
2. `assurance/source/*.json` for normative historical contracts; `assurance/ledger.json` + `assurance/case.json` for current states, only after evidence promotion.
3. `config/evidence-policy.json`, `config/required-tests.json`, `config/mutation-catalog.json` for mandatory claims/oracles.
4. Owner and real environment evidence per `config/external-evidence-policy.json`.
5. This dossier is a dated interpretation layer. In any conflict with source/evidence, HOLD and investigate; do not automatically adopt prose.

## Scope boundaries and existing controllers

- #4: dual-theme and accessibility product requirements.
- #6: runtime, T1–T7 external operational closure.
- #15: evidence supervisor, GPT successor and file-level conflict rules.
- #21: canonical audit backlog and dependency coordination.

**Not in scope unless separately contracted:** CMS, new billing/payment, user accounts, ERP replacement, real-time fleet availability or extra landing pages.

**Mandatory discipline:** smallest counterexample → RED oracle → minimal implementation → GREEN under exact source → negative mutation → full evidence → independent acceptance. No unsupported PASS, no direct push to main, no unapproved production changes.
