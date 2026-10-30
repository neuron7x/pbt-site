# Security verification register (partial; NOT certification)

**References.** [OWASP ASVS 5.0.0](https://asvs.owasp.org/downloads/) is the
published stable release; see [V15 concurrency](https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x24-V15-Secure-Coding-and-Architecture.md)
and [V16 logging](https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x25-V16-Security-Logging-and-Error-Handling.md).
[NIST SP 800-218 / SSDF 1.1](https://csrc.nist.gov/pubs/sp/800/218/final)
is final; Rev.1 / SSDF 1.2 was still a **draft** in October 2026.

| Scope | Executable evidence at exact PR HEAD | What remains unverified |
| --- | --- | --- |
| ASVS v5.0.0 V15.4.1 / V15.4.3 / V15.4.4, concurrent resources | `server/app.py` bounded semaphore, `_db_lock`, bounded delivery pool; `tests/test_hardening.py`, `tests/test_leads.py` race and delivery faults | Formal L3 coverage, load starvation across deployment |
| ASVS v5.0.0 V16.4.1, log injection | `_OneLineFormatter`; `test_request_log_strips_control_characters` | Rotation/retention, secure log transport and full inventory |
| API input / replay / transport controls | `tests/test_request_body_deadline.py`, `tests/test_api.py`, `tests/test_leads.py`; actual HTTP sockets, HMAC and persisted idempotency | Broader ASVS control coverage, external penetration test |
| SSDF 1.1 PW.7 / PW.8, code analysis/testing | Native+pytest+browser/visual CI; exact source SHA, immutable workflows, replay and mutation/fault tests | Full independent static code-analysis suite; audit of non-Python dependencies |
| SSDF 1.1 RV.1, vulnerability monitoring | Pinned `pypa/gh-action-pip-audit` scans hash-locked Python test packages against OSV on each PR; no ignored findings; preserves SHA-bound receipt | Continuous post-release monitoring, system packages, JS vendor assets, CVE triage |

**Verification boundary:** this project is not claiming ASVS 5.0 certification,
NIST SSDF conformance, absence of vulnerabilities, production readiness, or
successful recovery under 30-minute faults. A green dependency-audit job only
establishes that its pinned scanner completed and found no unignored advisory
for the scanned locked Python packages at that time; outages and indeterminate
scans are blocking, not successes. Inspect the actual GitHub job and
`artifacts/security/osv-receipt.json` for matching exact HEAD and scanner outcome.

Owner-only: visual design, tariffs/VAT and production release decisions.

## Additional scoped AST gate (not a substitute for SAST)

`tools/security_static.py` parses **server/** and **ops/** Python via stdlib AST,
rejecting eval/exec, unsafe deserialization, shell subprocesses and network
calls without explicit timeouts. `tests/test_security_static.py` inserts
adversarial code mutants and checks each is rejected. CI emits an exact-head
`pbt-static` evidence artifact and fails on missing/invalid input. This is a
narrow source hygiene guard, **not** broad static analysis or ASVS certification.
