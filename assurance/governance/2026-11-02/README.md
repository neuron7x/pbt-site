# PBT · Repository-backed tasks, acts and protocols

**Status:** versioned **execution documentation**, not production rollout. **Historical snapshot source** `main@dd85775749e28cf35c2e0c80c188b5dfbda21add` (2 November 2026); any later merge must be reverified at its new SHA. This directory is isolated from existing [Draft PR #22](https://github.com/neuron7x/pbt-site/pull/22) `docs/audit/**` and [Draft PR #28](https://github.com/neuron7x/pbt-site/pull/28) `assurance/evidence/**`.

| File | Deliverable |
|---|---|
| [01_TASK_REGISTER.md](01_TASK_REGISTER.md) | All 48 W0–W5 normative task IDs + RED counterexample, dependencies, acceptance predicate and current ledger state |
| [02_ENGINEERING_ASSURANCE_ACT.md](02_ENGINEERING_ASSURANCE_ACT.md) | Source-scoped act with exact SHA, native run IDs, observed scope, previous independent bytes and explicit limitations |
| [03_VERIFICATION_PROTOCOL.md](03_VERIFICATION_PROTOCOL.md) | Operational RED→GREEN→MUTATION, original ZIP/JUnit/soak, handoff, branch ownership, guarded merge and postmerge protocol |
| [04_EXTERNAL_EVIDENCE_ACT.md](04_EXTERNAL_EVIDENCE_ACT.md) | 18 externally blocked technical contracts, B1–B9 owner source requirements, authentic receipt schema |
| [05_EXECUTION_BOARD.md](05_EXECUTION_BOARD.md) | Non-duplicative, actionable parallel tasks and workstream ownership, linked to controllers |
| [06_TASKS_SNAPSHOT.json](06_TASKS_SNAPSHOT.json) | Machine-readable immutable source projection of all 48 tasks; not a substitute for normative ledger/receipts |

Canonical control: [#15](https://github.com/neuron7x/pbt-site/issues/15); tracked audit actions [#21](https://github.com/neuron7x/pbt-site/issues/21); runtime/owner [#6](https://github.com/neuron7x/pbt-site/issues/6); visual/UX [#4](https://github.com/neuron7x/pbt-site/issues/4). Original immutable specification is `assurance/source/tasks.json`; current committed ledger remains `pre_integration`. Current accepted engineering evidence is revision-bound. **No signed owner decisions are created by a GPT document. No production deployment or CRM mutation.**
