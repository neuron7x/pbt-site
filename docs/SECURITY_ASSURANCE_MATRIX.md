# Security assurance evidence matrix — PBT PR #8

Evidence is evaluated at the **exact PR HEAD** in CI; older commits are not
evidence for the current source. Source standards: [OWASP ASVS 5.0.0]
(https://asvs.owasp.org/) (stable May 2025) and [NIST SP 800-218 SSDF v1.1]
(https://csrc.nist.gov/pubs/sp/800/218/final). This is an engineering
traceability matrix, **not** comprehensive ASVS conformance, full SAST, an
external penetration test, or NIST certification.

| Control / threat | Falsifier or actual enforcement | Evidence gate | Assurance boundary |
| --- | --- | --- | --- |
| Exact-code provenance & dependency integrity | SHA-pinned Actions; hash-locked Python distributions; full diff hygiene | `pr-quality.yml`, `security-assurance.yml` | Does not independently prove system package provenance or all upstream build steps |
| Unsafe Python primitives & missing HTTP socket timeouts | AST scanning plus adversarial mutants including `build_opener().open` | `tools/security_static.py`, `tests/test_security_static.py` | Only server + ops source, **not** comprehensive SAST; Python AST dataflow is deliberately narrow |
| Public POST lifecycle and quota exhaustion | Absolute request-body deadline; origin check; bounded rate identities; no partial persistence | `tests/test_request_body_deadline.py`, `tests/test_rate_resource_bound.py` | Synthetic HTTP clients; not full distributed abuse capacity |
| Webhook integrity and at-least-once delivery | HMAC-SHA256 negative tests, durable SQLite outbox, idempotency & 408/429/5xx retries | `tests/test_leads.py`, `tests/test_hardening.py` | External CRM verification and replay/deduplication not independently established |
| Slow response headers and stalled delivery slots | Parent-enforced process deadline, Linux parent-death kill, 51-item saturation/restart | `tests/test_delivery_deadline.py` | Local synthetic sockets, not third-party production latency or multi-node throughput |
| Known backup RPO gap / unapproved data loss | Reconcile issued-ID watermark; restore refusal before mutation; explicit break-glass | `tests/test_backup_safety.py`, `ops/restore.py` | Cannot reconstruct lost leads, protect against disk loss or prove RPO=0 |
| Backup durability, worker freshness | SQLite integrity + file/directory fsync injections; optional heartbeat | `tests/test_backup_safety.py`, `tests/test_worker_heartbeat.py` | Local disk, thread activity only; no off-host durability/CRM success guarantee |
| Dependencies & visual media | OSV pip-audit; SHA/CRC visual artifacts; synthetic browser checks | `security-assurance.yml`, `visual-evidence.yml` | OSV knowledge base coverage; synthetic LCP/CLS, no field INP |

## Remaining acceptance constraints

1. A separate *production* test must establish real CRM receipt, retry/dedup
   behavior, and an explicitly adopted downstream SLI/SLO. Local synthetic
   soak (even 1800 s) does not prove a production SLO.
2. Off-device backup replication and reconciliation evidence are required
   before any claim of bounded physical-disk-loss RPO. The current backup
   and `--allow-rpo-gap` flag do not provide zero-data-loss restoration.
3. Broad ASVS 5.0.0 requirements review and full CodeQL/SAST require a
   suitable private-repository security entitlement or an alternative
   independently pinned scanner. The five-file AST policy is not that.
4. Field INP/CWV, product policy (VAT/pricing), accessibility visual
   acceptance and deployment authorization remain separate.

Under solo-owner governance there is **no formal separate human reviewer
gate**. The repository is nevertheless kept Draft until outstanding material
engineering blockers meet the owner's conditional merge criteria.
