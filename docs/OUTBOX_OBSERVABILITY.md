# Outbox operational status — evidence boundary

The HTTP `/api/health` response remains unchanged: SQLite readability/writeability
and free disk space. It does **not** measure delivery lag, webhook availability,
or worker liveness.

A local, read-only operator CLI now exposes aggregate SQLite outbox state:

```sh
python3 ops/outbox_health.py --db data/leads.db --max-pending-age-s 600 --max-failed 0
```

**600 seconds is an example supplied by the operator, NOT an adopted production
SLO.** The maximum acceptable delivery age must be chosen and documented before
measuring a production service. Absence of `--max-pending-age-s` is invalid.

- Exit 0: observed pending age and failed counts satisfy the supplied policy.
- Exit 1: stale pending or too many terminal failures; do not treat as ready.
- Exit 2: missing/unreadable database or invalid policy; fail closed.
- Idle/local-only operation (no delivery rows) is valid but **does not prove**
  webhook configuration or worker liveness.
- `due` is rows eligible now, `pending` includes scheduled retries,
  `oldest_pending_age_s` measures age from accepted-lead creation, not just
  next delivery attempt. Output contains aggregate counters only.
- Worker heartbeat, real-user performance, end-to-end CRM acceptance, retention
  and recovery point objective (RPO) remain separate, unverified requirements.
- No secrets, payloads or contact details may be emitted.

This probe is neither ASVS certification nor NIST SSDF attestation.
