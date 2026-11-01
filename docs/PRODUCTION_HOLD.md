# Production HOLD register

**State: PRODUCTION HOLD.** The engineering release candidate cannot leave this state by more tests.
Each row needs a fact from outside this repository. Nothing here may be filled in by an agent.
Templates for receipts: `assurance/source/` (decisions) and the assurance package `evidence_templates/`.

| ID | Missing fact | Who | Blocks | Closes when |
|---|---|---|---|---|
| B1 | Approved, effective-dated tariffs (site prices date from 03.10.2026; 1C differs) | Owner | OPS-06, WEB-07 | Signed snapshot with date; validator run against it |
| B2 | VAT, minimum shift, idle, crane and dispatch policy | Owner | OPS-06, WEB-07 | Written decision |
| B3 | Live delivery channel and credentials; authorized live test | Owner | NET-04, DB-08 | Receiver receipt naming real lead ids; `ops/readiness.py --receiver-receipt` PASS |
| B4 | Domain, DNS, TLS, proxy chain | Owner | NET-02, OPS-07, WEB-06 | Independent DNS and TLS check; canonical and OG URLs set then, not before |
| B5/B6 | Rights to TikTok footage, authorship and origin of frames | Owner | WEB-08 | Per-asset rights record |
| B7 | Privacy notice, purpose, retention, lawful basis (Law of Ukraine 2297-VI) | Owner + lawyer | OPS-04, OPS-05 | Dated decision. No automatic deletion exists until then |
| B8 | Public email and Telegram | Owner | WEB-06 | `config/business.json`; today `null` means do not invent |
| B9 | Consent to Wikimedia illustration and attribution form | Owner | WEB-08 | Written decision |
| R1 | Off-device encrypted store and credentials | Owner | DB-07 | Provider receipt |
| R2 | Restore on a separate host, with RPO and RTO thresholds adopted before the run | Owner + operator | DB-08 | `ops/restore_drill.py` on that host, with receipt and external watermark |
| R3 | Decision to run under a system manager with a dedicated identity | Owner | NET-08 | Install `ops/systemd/system/pbt-site.service`; `sandbox_probe --manager system` on the target |
| H1 | Named human accessibility evaluation, screen reader, iOS Safari, real devices | Human evaluator | WEB-01, ADV-07 | Signed matrix |
| F1 | Field INP and CWV. Impossible before exposure | Owner | WEB-03, OPS-02 | Authorized bounded pilot, privacy-approved measurement |
| S1 | Adopted SLO before measuring | Owner | OPS-02 | Policy dated before the data |
| D1 | Explicit deployment authorization for a named SHA | Owner | OPS-07, OPS-08, ADV-08 | Authorization record |

Per the release protocol, a controlled pilot may start with F1 open only under separate authorization with limits and a rollback plan. No agent starts it.
