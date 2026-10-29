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

## Recovery point boundary

A healthy SQLite online snapshot is not a zero-RPO durable replica. If storage
fails after a backup, accepted leads committed after that snapshot are absent
from it; an operator must reconcile this gap from independently retained logs
or downstream records. Never claim lossless recovery from scheduled snapshots.

Backup creation fails closed for missing source databases, invalid retention,
corrupt snapshots and name collisions; it never silently replaces an earlier
recovery point. A restore must use a verifiable upper ID watermark (logs and/or
`--min-seq`) to avoid reusing an already issued CRM lead ID.
