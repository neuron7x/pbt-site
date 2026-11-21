# PLAINBUD ↔ PBT CRM · bidirectional integration roadmap

**Status:** PLANNED / NOT YET IMPLEMENTED · 2026-11-21  
**Canonical tracking:** [Issue #38](https://github.com/neuron7x/pbt-site/issues/38)  
**Scope owner:** product owner and authorized CRM implementation team. This document is a target architecture and staged integration contract, not a statement of current live connectivity.

## 1. Product intent and boundary

The PLAINBUD website is the **public customer-facing interface** of one CRM-driven operational ecosystem. The website should not become a second, independently edited business database or an alternative CRM. A customer can inspect products, obtain a qualified estimate, send a request, and eventually see explicitly authorized status information. Staff continue to manage clients, dispatch, approvals, inventory, pricing and deals in CRM.

```text
Customer
  | browse, select, quote, submit
  v
PLAINBUD Web / API
  |  (A) durable lead + signed, retried delivery
  +---------------------------------------------> PBT CRM
  |                                                  |
  | (B) vetted read-only projection of business data |
  <--------------------------------------------------+
  |
  +--- (C) optional authenticated customer status (not public PBT-id lookup)
```

**Important distinction:** two-way information flow does **not** grant bidirectional database write access. Every entity has one authority, and each integration endpoint has narrow purpose and least privilege.

## 2. Actual baseline versus future features

| Function | Current repository evidence | Future requirement |
|---|---|---|
| Website form → SQLite | Implemented in `server/app.py` with idempotency and durable outbox | Retain existing site-generated lead reference and auditability |
| SQLite → CRM | Configurable signed webhook transport with retry to the documented `/api/v1/site/leads` | Verify real CRM acknowledgement, deduplication and failure reconciliation in an authorized environment |
| Public catalog/quote | Locally packaged dataset and calculator | Receive **owner-approved** catalog and tariff rules from CRM while preserving offline UX |
| Available fleet/dispatch | Not verified as live | Publish only authorized, fresh availability; never promise a booking from a stale view |
| CRM order status → user | Not implemented | Explicitly scoped, authenticated access; avoid public reference enumeration |
| CRM record modification from site | Not part of the current wire | Only narrowly specified commands, if later authorized; no direct admin API access |

Existing `PBT-000001` references, `X-PBT-Signature`, request enums and length bounds are compatibility constraints. **Do not change these** without a separate CRM-side contract review and migration. This plan does not imply access to the separate private CRM repository or to customer data.

## 3. Authority, ownership and conflict policy

| Domain | Authoritative system | Website behavior | Fail-closed rule |
|---|---|---|---|
| Approved fleet catalog, material SKUs, unit definitions | CRM after owner approval | Versioned public read model; preserve visual presentation | Reject invalid/partial snapshot and report last valid revision |
| Prices, currency, VAT, minimum shift, transport tariffs, validity | CRM / owner approval | Render only approved effective-date rules; distinguish estimates from offers | Outdated/unknown pricing → request a quote, not false confirmed total |
| Availability, reservation, dispatch | CRM dispatch | Present a freshness-qualified public status only if explicitly enabled | Unknown/stale → `Уточнюється` |
| Lead created via website | Website SQLite: original `site_lead_id` and immutable payload | At-least-once transport; CRM stores site key and unique reconciliation mapping | Lost response/retry cannot create a second logical lead |
| CRM deal, assignment, operator notes | CRM | Do not include in public cache | Customer endpoint returns strictly whitelisted status only after authorization |
| Website brand, dual-theme layout, motion, marketing media | Website | Owned by website product/design | CRM cannot rewrite templates, scripts or asset paths |
| Privacy, contact retention, consent and access | Owner-approved policy & data stewards | Only purpose-limited fields allowed | Do not infer consent or introduce automatic deletion without approval |

**Consistency:** website and CRM are two services with potentially intermittent connectivity, not one atomic transaction. Prefer explicit monotonic revision IDs plus `updated_at`/`effective_at`, transactional snapshot replacement and idempotent event ingestion. Never overwrite a newer accepted version with an older response.

## 4. Proposed integration contracts — NOT deployed endpoints

These are schema decisions to be made jointly with CRM developers; no invented endpoint here becomes normative:

- **Inbound LeadReceipt:** keep the existing JSON payload, signed HMAC envelope and stable site ID. Agree on external site ID uniqueness, request/content digest, returned CRM ID, persisted/deduped status and replay semantics. Delivery is *at least once*, logical storage should be deduplicated; network "exactly once" is not a valid guarantee.
- **Outbound PublicCatalogSnapshot:** proposed fields `schema_version`, `revision`, `generated_at`, `effective_at`, `expires_at`, public catalog objects and separately approved quote rules. Field schema and endpoint name **TBD through CRM owner review**. Whole snapshot is authenticated, validated and atomically swapped; no public secret, client PII, internal markup or staff data.
- **AvailabilityProjection:** proposed catalog ID, public-safe category/state, as-of timestamp, validity interval. Only dispatch-backed values, no inventory mutation or reservation without an authorized protocol.
- **CustomerStatusProjection:** proposed opaque expiring capability or user-authenticated access to allowlisted states. No lookup using a bare sequential `PBT-...` reference. Apply per-object authorization, rate limiting, anti-enumeration and redaction; explicit privacy decision required.
- **Compatibility and migration:** versioned consumer-driven tests, fixtures for both old and new versions, explicit deprecation window, isolated rollout/rollback. Site must work without CRM response; unavailable pricing or availability must be visibly marked as unconfirmed rather than silently served as current.

## 5. Adversarial invariants / acceptance

- **I-01: Lead durability.** A committed website lead is never silently discarded because CRM is offline. Outbox retries and manual reconciliation preserve the same site ID.
- **I-02: Logical uniqueness.** Replays, lost acknowledgements, timeouts, duplicate events and concurrent delivery yield one logical CRM lead per website source key; independently reconcile IDs and signed payload digest.
- **I-03: Single writer for business facts.** CRM is authoritative for active catalog, price and dispatch; website caches do not write back business decisions.
- **I-04: Explicit freshness.** Revision and validity are checked before public publishing. Stale/clock-skewed/partial snapshots fail safely and are observable; the maximum allowed staleness is a future owner-approved SLO, **not an invented numeric threshold**.
- **I-05: Least privilege.** The website cannot read internal CRM records, adjust tariffs or expose customer PII. Public status requires authorization; IDOR, cross-tenant reference guessing and token replay are negative controls.
- **I-06: Contract continuity.** Existing `PBT-*` references, `X-PBT-Signature`, lead enums and old clients remain functional under migration.
- **I-07: Recovery.** Rollback, restore after power loss, backlog replay, failed snapshot application and duplicate events preserve consistency; raw contact data never enters logs or assurance artifacts.
- **I-08: Evidence.** Tests cover both directions and independent source-bound receipts. Synthetic receiver success does not count as live CRM acceptance, green CI does not prove production SLO, and a diagram cannot close a release gate.

**Required falsifiers:** bad signature/rotated key, duplicate lead, changed payload for same key, lost 201, out-of-order revisions, partial snapshot, corrupt JSON, client token enumeration, expired capability, invalid VAT rule, CRM outage, rate pressure, reboot mid-sync, stale pricing, recovery and rollback. Record failing baseline → patch → passing controls and a test showing the dangerous mutation is rejected.

## 6. Milestones & dependencies

| Gate | Output | Preconditions and independently observed Done |
|---|---|---|
| C0 | Current protocol inventory | Inspect both sites' real code with permission; freeze existing site contract; record incompatibilities |
| C1 | Signed-off schema, owner matrix, test fixtures | CRM team approves schema, authentication, permissions, privacy classes, versioning, loss semantics |
| C2 | CRM → website catalog and price projection | Atomic local cache, validation, freshness and deliberate offline behavior; contract/negative tests |
| C3 | Quote and availability integration | Owner-approved tariff/VAT/minimum/transport policies and dispatch availability; no misleading total or booking |
| C4 | Authenticated customer status (optional) | Approved lawful basis and scoped access; IDOR/fuzz/expiration negative controls |
| C5 | Operational resilience | Backlog/dead-letter/reconciliation procedures, backup and restore, monitoring without PII; measurable owner-adopted SLO |
| C6 | Independent release evidence | Full source-bound CI, security, browser/visual, simulated network failures, authorized CRM staging/live acceptance and rollback |

Implement **C0–C1 before changing endpoints**, then read-only CRM → site (C2), then stronger business semantics (C3), then optional customer identity (C4). A site-side feature is not considered complete without reciprocal CRM contract tests.

## 7. Project integration and commercial scope

- [Issue #38](https://github.com/neuron7x/pbt-site/issues/38) is the roadmap register; link future implementation PRs to the relevant C-gate, not to a vague completion percentage.
- Current [brand/engineering PR #34](https://github.com/neuron7x/pbt-site/pull/34) is **DRAFT**; [runner blocker #35](https://github.com/neuron7x/pbt-site/issues/35) still prevents verified merge. Keep the current website→CRM contract untouched while completing current gates.
- Owner-dependent decisions in [PRODUCTION_HOLD.md](PRODUCTION_HOLD.md) (B1–B9, privacy, live receiver, TLS, offsite restore, human review, deployment signoff) remain blockers; no agent can self-authorize them.
- This **new bidirectional integration is separate incremental scope** relative to the current completed-site price estimate. Itemize work, ownership and commercial change request before implementing C2–C6; do not silently count future functionality as already delivered.
- Original premium visual concept stays intact: two themes, animations, source media, quote UX. CRM integration is under the hood, not an aesthetic redesign.

**Exit condition:** one customer-facing system with consistently governed business facts, reliable bidirectional *information* flow, verifiable contracts, safe offline states and permitted customer access—not merely two services connected by an unverified webhook.
