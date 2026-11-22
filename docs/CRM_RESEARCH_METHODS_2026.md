# 2026 Research-to-Engineering Protocol · PLAINBUD ↔ PBT CRM

**Decision-support research · 21 Nov 2026 · status: proposed / not release approval**  
**Canonical product intent:** [Issue #38](https://github.com/neuron7x/pbt-site/issues/38) · [CRM Jira KAN-158](https://neuron7x.atlassian.net/browse/KAN-158) · [Implementation roadmap](CRM_INTEGRATION_ROADMAP.md).  
**Binding stage decision:** [ADR-0001](ADR-0001-INTEGRATION-SEQUENCE.md). The v1 policy is deliberately non-authorizing; research is not a live release.  
**Evidence boundary:** source and Jira checks reflect accessible records as of 21 Nov 2026. A Jira "Готово" label is a workflow claim, **not** an independently executed live site↔CRM acceptance test.

## Owner sequencing constraint (binding for this research program)

**Decision:** finish CRM first; then finish the website as a complete independently operating product; **only when BOTH pass their separate acceptance gates**, authorize and begin the actual integration. The website's existing local intake/outbox and static catalog must not need a running CRM to remain usable. Do not interpret the pre-existing webhook transport as an instruction to activate it against production.

Until then, every methodology below is **research / deferred design**, not a current implementation task. C0 implementation inventory and compatibility testing start in the integration phase after the two independent products are finished; source reading for risk analysis may occur earlier without writes. This does not weaken either product's tests or their independent release/production holds.

## 0. Research discipline

Selection criteria: influential primary research (prefer peer-reviewed or authors' published work); current normative specifications; original engineering patterns; no junior tutorials or unexplained marketing methodology. Distinguish **publication year** from **2026 applicability** and label research claims as *theory*, *pattern*, *specification*, or *locally observed Jira fact*. Cite the direct publication, not an influencer biography. No paper itself proves this repo correct.

**Do not cargo-cult scale.** This is one company's website plus a separate CRM. A broker, Kafka, microservice mesh, streaming cluster, CRDT, distributed-systems framework, or AI swarm has **no automatic justification**. Start with the existing stdlib web server + SQLite durable outbox + authenticated CRM webhook; add a bounded public read-model only when actual CRM interfaces and business authorization exist.

## 1. High-caliber research / protocol selection

| ID | Author / publication and verified date | What the source actually establishes | Engineering adoption here | Evidence we must produce; boundary |
|---|---|---|---|---|
| R1 | **Martin Kleppmann, Chris Riccomini**, *Designing Data-Intensive Applications*, 2nd ed., O'Reilly **Feb 2026** · [publisher](https://www.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/) | Architectural tradeoffs; systems of record vs derived data; replication, storage and consistency perspectives | CRM owns authoritative mutable catalog/prices/dispatch; website holds rebuildable versioned public projection and local lead intake | Source-of-truth/field-ownership matrix; revision reconciliation; never assert strong consistency across disconnected services |
| R2 | **Pat Helland**, *Life Beyond Distributed Transactions*, **CIDR 2007** · [paper](https://ics.uci.edu/~cs223/papers/cidr07p15.pdf) | **Position paper**, not a theorem guaranteeing our code; reasons about entities and inter-entity messaging without global transactions | Treat site and CRM as independent fault domains with explicit messages, durable local atomic writes and reconciliation; avoid cross-service 2PC | crash after site commit/before send; crash after CRM receipt/before ACK; no missing logical lead |
| R3 | **Chris Richardson**, *Transactional Outbox* · [original pattern](https://microservices.io/patterns/data/transactional-outbox.html) | Sender stores an outbox message atomically with local change; relay may send duplicates; consumer must be idempotent | Preserve site's current SQLite lead+outbox transaction; CRM dedup by stable source ID, payload digest and tenant/source | Lost ACK, restart and simultaneous retry tests: one logical CRM row, no untracked pending lead; **not** exactly-once network delivery |
| R4 | **Peter Bailis, Alan Fekete, Michael J. Franklin, Ali Ghodsi, Joseph M. Hellerstein, Ion Stoica**, *Coordination Avoidance in Database Systems*, **PVLDB vol.8(3), 2014; VLDB'15 presentation** · [paper](https://www.vldb.org/pvldb/vol8/p185-bailis.pdf) | **Invariant confluence** identifies when concurrent operations can preserve invariants without coordination; some operations need serialization | Read-only public snapshots may be asynchronously replicated; inventory reservation, financial mutation, price approval and state transitions require authoritative coordination | Per-command invariant list and counterexample showing why a stale replica cannot confirm booking |
| R5 | **Leslie Lamport**, *Specifying Systems*, **2002** · [publisher / TLA+](https://www.microsoft.com/en-us/research/publication/specifying-systems-the-tla-language-and-tools-for-hardware-and-software-engineers/) | Formal specification and TLC model checking for finite models | Optionally model minimal site/CRM state machine, lost ACK and revision ordering before implementation | TLC run against a **finite declared bound**; counterexample trace for broken variants. No formal proof claimed before running it |
| R6 | **Kyle Kingsbury, Peter Alvaro**, *Elle: Inferring Isolation Anomalies from Experimental Observations*, **PVLDB 14(3):268–280, 2021**, DOI 10.14778/3430915.3430918 · [paper](https://www.vldb.org/pvldb/vol14/p268-alvaro.pdf) | Infers certain transaction isolation anomalies from client-observed histories and adversarial workloads; **not a generic HTTP API certification tool** | Adopt Jepsen-style fault injection and independently checked operation histories for website↔CRM flows; use actual Elle only if suitable transaction-history datatypes can be generated | Raw event histories, independent invariant oracle, exception traces; no claim that Elle tests our CRM without actual run |
| R7 | **Ramaswamy Chandramouli, Zack Butcher**, NIST **SP 800-228 update 1, 13 Mar 2026** · [official](https://csrc.nist.gov/pubs/sp/800/228/upd1/final) | Risk-based API protections across pre-runtime and runtime, including appended risk/control indexes; supersedes June 2025 release | Inventory public/admin interfaces, risks, per-operation authentication and authorization, TLS, rate bounds, secret rotation, negative security controls | API risk matrix and tested controls. NIST guidance != NIST certification |
| R8 | **OWASP ASVS**, **5.0.0, 30 May 2025** · [official](https://asvs.owasp.org/) | Testable web app/security requirements | Map API-level access, data validation, cryptographic storage, logging and error cases to exact ASVS control IDs during contract review | Test ID → specific requirement → evidence; don't claim all ASVS 5.0 passes from isolated tests |
| R9 | **OpenAPI Initiative**, **OAS 3.2.1, 10 Sep 2026** · [normative specification](https://spec.openapis.org/oas/v3.2.1.html) | Standard HTTP API contract notation; language-neutral interface | Versioned schemas for CRM read projection and existing inbound lead; consumer-driven fixtures, backward compatibility, error shapes | Schema validation on both sides, old-client compatibility and schema-drift gate. Select tool-support version deliberately; v3.2.1 support must be verified in chosen toolchain |
| R10 | **Mark Nottingham, Erik Wilde, Sanjay Dalal**, **RFC 9457, Jul 2023** · [IETF](https://www.rfc-editor.org/rfc/rfc9457.html) | Machine-readable HTTP API error format | **Proposed new endpoints only:** typed error details, retryability contracts, stable error identifiers; **do not unilaterally rewrite existing** `/api/lead` JSON error contract | Negative tests on 400/401/403/409/429/503 and no personal data in error body |
| R11 | **CNCF CloudEvents 1.0.2** · [specification](https://github.com/cloudevents/spec) | Standard envelope for event interoperability | **Optional** if integration adds many independent consumers: event ID, source, type, subject, time, schema version; not mandatory to deliver a single signed HTTP webhook | Contract/consumer compatibility; reject duplicate event id and unknown type. Do not introduce a broker without measured need |
| R12 | **OpenTelemetry** HTTP spans · [semantic conventions](https://opentelemetry.io/docs/specs/semconv/http/http-spans/) | Stable HTTP span conventions (umbrella HTTP specification has mixed status) | Trace event lifecycle with structured request/operation IDs and aggregate latency/failure metrics, without client contacts or raw payload | Non-PII telemetry redaction tests; sampling and retention policies approved by owner |
| R13 | **NIST SP 800-218 v1.1**, *Secure Software Development Framework*, **2022** · [official](https://csrc.nist.gov/pubs/sp/800/218/final) | Secure development practices, not an automatic release claim | Threat model/CI gate/evidence provenance and controlled rollbacks | Exact-head source+test+artifacts, negative controls and documented acceptance |

**Reconciliation:** Bailis' coordination avoidance is *conditional* on explicit invariants. It does **not** mean allowing offline updates to money, inventory bookings or deal states. TLA+ and Elle operate at different levels: model checking planned state-machine behavior versus examining observed transactional histories; do not conflate them. The 2026 novelty lies primarily in the **Feb 2026 DDIA edition, Sep 2026 OAS 3.2.1, and Mar 2026 updated NIST API guidance**; older seminal theories remain applicable.

## 2. Requirements extracted from PBT CRM Jira (not inferred from a screenshot)

| Jira source / accessible state at read | Specific decision / fact | Consequence for website integration |
|---|---|---|
| [KAN-113](https://neuron7x.atlassian.net/browse/KAN-113), **Готово**, updated 06 Nov | Site-generated leads enter CRM as incoming; a **human** creates the deal. Source says 20 added tests | Current lead wire stays stable; do not treat receipt as order, deal or payment |
| [KAN-6](https://neuron7x.atlassian.net/browse/KAN-6), **В роботі** | Manager workflow: classify lead, buyer/supplier/advance, in-progress and payment states; completed means paid | Build explicit *CRM → public status* transition whitelist; no public exposure of internal columns, supplier cost or margin |
| [KAN-4](https://neuron7x.atlassian.net/browse/KAN-4), **В роботі**, decision registry | D-05: eight lead states/six board columns. Later D-37 changed manager visibility of purchase/margin; D-38–D-40 assign payment authority and limit visibility | **Conflict gate:** KAN-6's earlier scenario says manager sees no margin; later D-37 says manager can see it. Determine the authoritative effective ACL from code + latest approved decisions; never copy either into public scope without owner confirmation |
| [KAN-33](https://neuron7x.atlassian.net/browse/KAN-33), **В роботі** | Counterparty dedup requires debt totals and lead count preserved; repeated merge is no-op | Site cannot merge identities on its own; stable external IDs, not company name |
| [KAN-34](https://neuron7x.atlassian.net/browse/KAN-34), **В роботі** | Equipment capacity/maintenance checklists not fully finished | Do not advertise real-time 'available' or a guaranteed reservation from unverified dispatch data |
| [KAN-140](https://neuron7x.atlassian.net/browse/KAN-140), **Чекає рішення** | Per-item price mandatory before departure is deferred (D-19) | Avoid coupling public quote to an unapproved line-item accounting requirement |
| [KAN-142](https://neuron7x.atlassian.net/browse/KAN-142), **Чекає рішення** | Telegram bot classifies direction via operator (D-22); button change deferred | Website type enums remain stable; CRM operator still decides workflow meaning |
| [KAN-41](https://neuron7x.atlassian.net/browse/KAN-41), **До виконання** | Server, offsite backup, domain and Telegram operator decisions missing | No live deployment, TLS/domain or offsite-recovery claims |
| [KAN-147](https://neuron7x.atlassian.net/browse/KAN-147), **В роботі** | G1–G7 evidence gates, multi-role day and night acceptance; G8 external backup deferred | CI/soak proof of site cannot substitute for the CRM's operational acceptance |
| [KAN-148](https://neuron7x.atlassian.net/browse/KAN-148), **В роботі** | 76 consultant requirements; reported status mix (not all implemented), static review and limited measured tests | Public interfaces must not promise an unverified requirement |
| [KAN-132](https://neuron7x.atlassian.net/browse/KAN-132), **Готово** | Three evidence layers: source, CI and Jira change audit | Correlate source SHA/contract revision/Jira decision to tests and a real receiver, preserve independently checkable receipts |

**Important discrepancy:** Jira records last shown as updated by **16 Nov 2026**, not evidence of code state on 21 Nov. PR #34 documents the site-side transport, but this does **not** confirm real CRM receiver/endpoint operation. New work must first inspect current CRM source with authorization (C0).

## 3. Derive the minimal correct architecture

```text
Visitor ─POST→ Website: validate + commit (lead, outbox) atomically
                     │             │
                     │ durable ID  └─ asynchronous signed delivery ──→ CRM Inbox
                     │                                         │
                     └─ 201 site receipt                dedup + decision by human
                                                                   │
   Website public-cache ← trusted, versioned projection ← CRM approved catalog/prices
                                                                   │
   Website customer status ← scoped authenticated projection ← CRM state (optional)
```

**Safety vs liveness:** website can promise `201` only if its **own** lead storage commits. It cannot promise live CRM acceptance unless CRM provides an independently reconciled confirmation. Under unbounded outages there is no unconditional delivery-liveness guarantee. Once network and receiver recover, fair retrier and valid credentials can support an eventual-delivery target, to be tested rather than declared.

**Source-of-truth constraints:** CRM owns approved price, dispatch and financial decisions; website owns presentation and original lead intake. Identical entity identifiers do not imply permission to edit both sides. Use a separate immutable external `site_id` identity, never match on customer name alone.

**Consistency:** public cache is derived, with a monotonic CRM-issued revision, timestamps, validation and atomic swap. If an update is stale, out of order or malformed, never overwrite a newer valid snapshot. A previously valid snapshot may be shown **only if** effective-date/freshness/policy permits it; otherwise suppress precise live availability/tariff and offer manual confirmation.

**Failure handling:** no global transaction or hidden synchronous dependency from `/api/lead` to CRM. Accept locally, enqueue, retry boundedly, record delivery state. CRM receiver must deduplicate repeated messages; source-side idempotency does not alone guarantee target-side uniqueness.

## 4. Invariants as executable obligations

| ID | Formalized safety property (must never be violated) | Negative test / oracle |
|---|---|---|
| F1 | `site.commit(lead) => exists site.outbox(lead)` within same DB transaction | Inject crash between insert/outbox; no committed lead with missing delivery intent |
| F2 | `∀ tenant,siteId: count(CRM logical records for key) ≤ 1` | Duplicate signed POST, retries, reordered replay, concurrent receiver workers; reconcile CRM rows |
| F3 | `crmDealCreated => actor is authorized human/workflow` | Site message cannot create a deal or bypass approval/advance rule |
| F4 | `publishedRevision ≤ sourceAuthoritativeRevision` AND never regress `publishedRevision` | Out-of-order snapshot, equal revision with different digest, clock skew, partial download |
| F5 | `publicFields ⊆ ownerApprovedAllowlist` | Inject supplier price, client PII, margin, account numbers, payroll into fake CRM payload; reject |
| F6 | `publicAvailability='confirmed' => fresh authorized dispatch proof` | CRM outage, stale availability, unverified inventory, two parallel reservation attempts |
| F7 | `moneyMutation => role ∈ approvedOwners` at **effective ACL revision** | Role tests per D-37–D-40 and code; manager/public must not mutate payments |
| F8 | `publicStatusRead => valid scoped authorization, not bare sequential PBT ref` | IDOR, cross-tenant replay, expired opaque capability and reference enumeration |
| F9 | `site outage/restart preserves unique lead + outbox intent` | Kill during commit, restart, multiple retriers, backup/restore and receiver dedup |
| F10 | `source/target evidence SHA+schema revision match deployment candidate` | Tamper artifacts, mix old SHA logs, missing negative controls => gate HOLD |

**Liveness goals** (e.g. public snapshot age, eventual queue drain, RTO) require an **owner-approved measurable time bound**. Do not fabricate an SLO in this document. Test deadlines against synthetic fault schedules and, later, permitted real staging.

## 5. Exact acceptance protocol (not 'LLM reviewed')

### Gate A — inventory / adversarial design before code
1. Inspect **current** site SHA and authorized current CRM code/config; enumerate public/private objects, actor roles, existing route and webhook receipt semantics.
2. Maintain a 4-column decision record: `claim → Jira source/effective decision → exact code → independent test`. If evidence conflicts or is missing, status `UNKNOWN/HOLD`, not `PASS`.
3. Review scope and owner approval: catalog read model not yet the billing engine; stock/availability requires dispatch decision; public status is a separate privacy surface.

### Gate B — contract-first
4. Propose versioned OpenAPI document (3.2.1 **only if validators support it**); preserve existing `X-PBT-Signature` and receipt wire. Add requested operation/response schemas and negative error cases without changing legacy clients.
5. Generate consumer-driven tests against a **synthetic CRM mock** and a separately implemented CRM adapter; no production credentials. Test invalid enums, Unicode, size limits, replay digest, forbidden fields, stale versions and backward compatibility.
6. Attribute code changes to one controlled owner/PR with exact base SHA. Do not edit CRM and site in two uncoordinated agent sessions.

### Gate C — model-based falsification
7. Write a small TLA+/TLC model with `SiteLead, Outbox, CRMRow, SnapshotRevision, Authority` states, actions `Commit, Dispatch, Receive, AckLost, Retry, Publish, Reorder, Crash, Recover`. Specify safety F1–F10 in relevant finite model and fair liveness only under declared network assumptions.
8. Run TLC with bounded identities/revisions and retain model/config/checker version, generated counterexample traces, source hash. **Not run yet.** The model covers logic, not correctness of the Python implementation.
9. Run randomized concurrent/fault-injected integration histories against the actual SQLite + CRM staging adapter. Independently reconcile client-observed outcomes with persisted rows. Use Jepsen/Elle *if it applies to chosen transactional operation model*; do not label generic HTTP probes 'Elle-verified'.

### Gate D — independent system evidence
10. Verify actual CRM implementation behavior on authorized **test data**, including crash after receive before ACK, exact `site_id` idempotency, reconciliation and no lost leads. Source-declared "Готово" is insufficient.
11. Test public read model: signed data, stable revision, atomic snapshot, no PII/finance leakage, staleness fail closed, explicit backup/rollback and business approval of tariff interpretation.
12. Security: per-object auth, input bounds, signed message verification, secret rotation, replay protections *with legacy compatibility*, rate limits, structured non-PII logs and authorization matrix against latest Jira decisions. Map to NIST SP 800-228 upd1 + OWASP ASVS 5.0 requirements; certification **not** implied.
13. CI: true runner execution, positive + negative test JUnit, independent artifact checksum, fixed exact source SHA, browser/accessibility tests and mandatory soak. No green historical SHA substitution. [Runner blocker #35](https://github.com/neuron7x/pbt-site/issues/35) still open.
14. Business release: owner-authorized domain/TLS, privacy, real receiver, prices/VAT, media rights, offsite restore and deployment SHA. Engineering approval is **not** production authorization.

## 6. Implementation priority / proportional complexity

**P0 — AFTER CRM AND WEBSITE INDEPENDENT COMPLETION:** read current CRM source with authorization, resolve effective ACL conflict and confirm inbound receipt semantics. Before both are ready: documentation/research only.  
**P1:** establish consumer-driven versioned contract and CRM read projection; verify refresh policy and its operational independence from site lead intake.  
**P1:** executable fault tests (duplicates, crashes, missing ACK, staleness, bad authorization), sign off database assertions.  
**P2:** public quote projection with approved VAT/minimum/dispatch rules.  
**P2:** optional authenticated customer status after business privacy decision.  
**Do not implement yet:** distributed message broker, event sourcing, public live reservation, AI-agent CRM data access, remote administrative write API or row-level mirroring—none is justified by available evidence.

## 7. Artifact checklist (future PRs must attach)

- `ADR-site-crm-authority.md` — effective Jira decisions, version and owner.
- `api-contract.yaml` — versioned endpoints/fields/errors, backward-compatibility and schema validator evidence.
- `integration-fixtures/` — synthetic good/evil envelopes; no PII or live credentials.
- `model/CRMBridge.tla` + TLC config + source-bound result **if** model checker adopted.
- `tests/contract_site_crm*` — receiver replay, role/IDOR, revision and crash/restore tests.
- `evidence/interop-report.json` — producer/consumer SHA, CRM build ID, event counts, duplicates, rejected bad cases and redactions, with immutable hashes.
- `ops/rollback-playbook.md` — explicit restoration, replay and no-data-loss response.
- Independent CI/provider-artifact and acceptance receipts, **not** self-asserted status.

**Bottom line:** adopt the *reasoning and falsifiers* of Kleppmann, Helland, Bailis, Lamport, Kingsbury/Alvaro, and the specific NIST/OpenAPI/OWASP standards. Do **not** equate adopting a name, a framework, or a pile of tests with proving the real two-way integration. The external business approvals remain [PRODUCTION HOLD](PRODUCTION_HOLD.md).
