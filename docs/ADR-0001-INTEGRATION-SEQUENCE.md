# ADR-0001 — CRM first, standalone website second, integration last

**Status:** ACCEPTED sequencing decision; **integration implementation DEFERRED**  
**Owner decision date:** 2026-11-21 · **Engineering specification:** 2026-11-22  
**Scope:** PLAINBUD public website and separately maintained PBT CRM.  
**Authority:** [GitHub decision #38](https://github.com/neuron7x/pbt-site/issues/38); [Jira KAN-158](https://neuron7x.atlassian.net/browse/KAN-158).  
**Related:** [2026 research protocol](CRM_RESEARCH_METHODS_2026.md), [product roadmap](CRM_INTEGRATION_ROADMAP.md), [production hold](PRODUCTION_HOLD.md), [platform CI blocker #35](https://github.com/neuron7x/pbt-site/issues/35).

## 1. Decision, not aspiration

1. **CRM first — independent closure.** Finish the current CRM backlog, financial rules, role authorization, operations and independent acceptance in its own source/CI/owner process. A Jira `Готово` label alone does not prove this gate.
2. **Standalone website second — independent closure.** Keep the current site fully usable without a live CRM: its own local accepted-lead store/outbox, static catalog, UI, privacy decisions, backup, media, performance and source-bound tests. A usable locally running website is not automatically authorized public production.
3. **Integration third — separately authorized.** Only after both products are independently accepted **and** the owner explicitly authorizes commencing integration, begin C0–C6 contract inventory, synthetic compatibility, public read models and fault testing. Live traffic requires an additional owner-issued release authorization and external proofs.

The *work priority* is ordered. Actual readiness is **not inferred by chronology**: the website may already operate locally while CRM is unfinished; CRM completion does not create a website acceptance receipt. Integration starts only on the conjunction of both independent evidence sets and owner approval.

## 2. First-principles model

There are two separately fallible systems, without a shared atomic transaction. Their authoritative data is not symmetric:

- **CRM:** approved business prices/VAT, machinery availability/dispatch, deals, internal status, finances, identity decisions.
- **Website:** customer experience, presentation/media, client interaction and durable originating site-lead ID.
- **Cross-boundary:** signed or mutually authenticated narrowly scoped interfaces, explicitly versioned; never database mirroring, public access to private CRM data, or unapproved price/booking claims.

Define `E_C` = CRM independent source/operational evidence accepted, `E_W` = website independent source/operational evidence accepted, `A_0` = owner authorizes starting integration.

```text
START_INTEGRATION := E_C ∧ E_W ∧ A_0
LIVE_CANDIDATE := START_INTEGRATION ∧ CONTRACT_OK ∧ STAGING_E2E_OK
                  ∧ SECURITY_PRIVACY_OK ∧ ROLLBACK_OK
                  ∧ PROVIDER_EVIDENCE_OK ∧ OWNER_LIVE_APPROVAL
```

These predicates refer to **independently verified** evidence, not claims placed in JSON, Jira labels, source comments, tests or model parameters. Even `LIVE_CANDIDATE=true` from a local simulator is **not an authorization**; a separate source-bound signed decision is required.

**State table**

| Operator work priority | Actual decision preconditions | Allowed work | Forbidden |
|---|---|---|---|
| `CRM_FIRST` | default; current state | Complete CRM and independently maintain/verify standalone site | Live site↔CRM activation, new two-way sync |
| `SITE_SECOND` | CRM externally accepted | Finish standalone website and its own release/operational gates | Start integration because CRM alone is green |
| `WAIT_OWNER_START` | CRM and site independently accepted | Record results and obtain specific integration authorization | Assume consent from prior Jira status or unverified artifacts |
| `INTEGRATION_THIRD` | both accepted plus owner start | Inventory, versioned contracts, mocks/staging, adversarial interoperability tests | Live production traffic without separate release authorization |

The actual canonical configuration, [`config/integration-lifecycle.json`](../config/integration-lifecycle.json), is intentionally frozen at `CRM_FIRST`, all readiness states `UNKNOWN`, and all **planned** integration channels disabled. It is not a runtime configuration nor a credential store.

## 3. Acceptance receipts must not be circular

**CRM evidence:** exact commit SHA, current scoped Jira decisions, role/finance state-machine tests, validated business rules, runtime recovery and independent operational proof; do not count website->CRM transport as CRM readiness.

**Website evidence:** exact commit SHA, real `make gate` and browser/media/security outcomes, locally durable leads without CRM connectivity, stable offline UX, owner decisions for public deployment. Existing [PRODUCTION HOLD](PRODUCTION_HOLD.md) (including B3, a valid *non-CRM* delivery route if standalone site is public, and B7 privacy) is **not waived**. Internal engineering acceptance and public launch are distinct.

**Start authorization:** specific owner acceptance of both evidence packages, named implementation scope and exact versions; acceptance must be independently obtained. Open Jira statuses, synthetic webhook 2xx, a generated report and the optional `LEAD_WEBHOOK_URL` code path are **not proof** of that acceptance.

**Live activation:** contract compatibility on both systems, data minimization/ACL, signed authenticity, real authorized test receiver, offline/replay/reconciliation, rollback plan, original CI/provider receipts and exact deploy SHA. No agent may generate owner approval or sign it on the owner's behalf.

## 4. Safety/liveness contracts and failure policy

- **S1. No premature coupling:** website must not require a live CRM for visitor interactions or for the local durable receipt. CRM outage is not a website availability failure when no live integration is authorized.
- **S2. No premature activation:** no new read-model sync, public CRM status, real credentials or live signed webhook traffic before external phase gate. Pre-existing optional site webhook **code** is retained only for compatibility; active production config is unobserved by this ADR.
- **S3. Lead honesty:** `201` on site means local SQLite commit, not remotely confirmed CRM acceptance; target-side idempotency after retries must be independently demonstrated.
- **S4. Single authority:** approval of money/availability stays in CRM. Client status is an optional authenticated projection; bare sequential `PBT-...` does not authorize disclosure.
- **S5. Monotonic readiness:** a later failed/revoked/stale artifact cancels its earlier PASS for a release target. No cherry-picking green historical SHAs.
- **S6. No pseudo-attestation:** a self-supplied PASS, LLM assertion or model enumeration cannot authorize integration or production.
- **S7. No secret leakage:** no customer records, server credentials, keys or production database content in repository/Jira/GitHub issue.
- **L1. Bounded recovery:** when receiver/network become available under explicit assumptions, outbox should eventually drain; real time bounds and SLO require owner approval and measurement. Unbounded outage means no unconditional delivery guarantee.

**Counterexample to reject:** a successful website `201` is followed by a lost CRM acknowledgement; a retry creates a second CRM deal. Prevention requires a durable site ID, target-side idempotency, and human deal creation; source tests alone cannot certify receiver behavior.

## 5. Executable policy checks: intentionally non-authorizing

`python3 tools/integration_sequence.py` validates exact schema, duplicate JSON keys, default frozen phase, all `UNKNOWN` signals, no declared activation, empty `LEAD_WEBHOOK_URL`/`LEAD_WEBHOOK_SECRET` in the checked-in environment template and this architecture's discoverability in `AGENTS.md`.

- Exit **0** = static plan is self-consistent and still **RELEASE HOLD**.
- Exit **1** = internally contradictory or malformed plan, **FAIL**.
- `python3 tools/integration_sequence.py --check-live` exits **2** for every structurally valid frozen plan because **independent external acceptance is not verified**.
- `python3 -m unittest discover -s tests -p 'test_integration_sequence.py'` covers malformed/ambiguous states, premature activation, source defaults and an exhaustive finite theoretical model of **3^9 = 19,683** combinations of `UNKNOWN/PASS/FAIL` claims. This is **not TLA+, formal correctness of Python runtime, a cryptographic signature check, a live CRM test or assurance release**.

The tool checks the **repository template**, not actual environment variables, deployed secrets, an operator's server, GitLab, CI or network. It **cannot technically stop a human from configuring a live endpoint outside Git**. Actual no-activation enforcement requires deployment permissions, an externally verified signoff and environment/operation controls; those remain pending and cannot be simulated into PASS.

## 6. Decision alternatives and rationale

- **Rejected:** link CRM to an unfinished website now → two simultaneously moving contracts, unclear failure ownership, false status/price risk.
- **Rejected:** mirror CRM databases bidirectionally → conflicting writers, exposure of customer/financial data, no justified need.
- **Rejected:** install Kafka/CRDT/microservice mesh as prerequisite → adds failure modes and operations burden to a small business workflow.
- **Chosen:** two independently accepted systems, deterministic contract boundary, minimal durable outbox, controlled projection and explicit activation approval. See Helland (2007), Bailis et al. (2014/2015), Kleppmann–Riccomini (2026), and source-bound test methodology in [research](CRM_RESEARCH_METHODS_2026.md).

## 7. Change control / next gates

1. **Now:** focus CRM closure and standalone website engineering; preserve all existing compatibility wires and design; no new integration runtime paths.
2. **After CRM gate:** verify website independently; this ADR remains non-authorizing even if CRM is ready.
3. **After both gates + owner start:** open a separate implementation scope/PR with signed-off contract, updated policy schema and independent proof verifier. Do not simply flip `UNKNOWN`→`PASS` in the static v1 JSON.
4. **After C0–C6:** authorized separate production acceptance and rollout. No live CRM linking through this ADR or the current documentation PR.

**Canonical effect:** future agents can read the decision and test its default policy. **Current effect:** planning only; neither CRM, the website production runtime nor the integration is certified complete.
