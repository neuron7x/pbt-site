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

## Optional worker-thread liveness (not delivery/readiness)

With a durable additive `runtime_heartbeat` marker, the delivery worker
records activity at most once every 15 seconds (configurable 1–60 seconds).
Use `ops/outbox_health.py --max-pending-age-s 600 --max-worker-idle-s 45`
for an **operator-selected** freshness policy. A missing marker returns UNKNOWN
(exit 2), a stale marker DEGRADED (exit 1). The CLI default remains unchanged,
and `/api/health` remains byte-contract compatible. A recent heartbeat is not
proof that CRM accepted leads; monitor failed/pending counts separately.

## Power interruption evidence boundary

The online SQLite copy is integrity-checked and fsynced before an atomic
create-only hard link publishes the snapshot. The backup directory metadata is
then fsynced before returning success; an injected file/directory fsync failure
returns nonzero. This improves crash durability but cannot guarantee RPO=0,
hardware trust, off-device replication or survival of disk destruction.


## Fail-closed known RPO gaps at restore

The restore tool **refuses with exit code 3** when an independently established
issued-ID watermark (server log or `--min-seq`) exceeds the last lead in the
selected backup. This detects **known** loss of accepted leads; merely advancing
`sqlite_sequence` is not recovery. On refusal the original database is not
replaced. Operators must reconcile missing leads from separately retained logs,
downstream receipts, or off-device records before deliberately using
`--allow-rpo-gap`. That break-glass flag **only** acknowledges the gap; it
cannot reconstruct contact details or outbox work. The result records the gap
count and is not a zero-loss attestation. Unknown missing records and a lost
journal cannot be disproved by a local backup.


## Heartbeat while processing saturated delivery batches

A worker can process 50 queued outbound jobs for longer than the configured
heartbeat freshness threshold. A heartbeat only after the entire batch or
multiple consecutive 50-row batches falsely marks a live worker as stale.
The worker now updates its *activity* marker at its configured cadence while
waiting on outbound futures and between batches, without holding the SQLite
write lock during network I/O. This is driven by the worker thread, not a
separate watchdog that might falsely report a dead worker as active.
Idle polling is also bounded by the heartbeat interval.

The regression schedules 51 durable outbox rows, stalls one delivery task,
and independently reads the SQLite heartbeat while the task remains blocked;
it then releases the task and checks all 51 rows drain without terminal
failure. A recent marker means the scheduler is active—not that the receiver
acknowledged the message, that work is making forward progress, or that
pending age is within policy. Operators must monitor `failed`, `pending`
and `oldest_pending_age_s` independently. Choose `--max-worker-idle-s`
greater than the configured heartbeat interval plus scheduler/SQLite jitter
(e.g. 45 s for the default 15 s interval); an interval of 60 s cannot satisfy
a 45 s freshness requirement. No live CRM or production SLO is implied.
