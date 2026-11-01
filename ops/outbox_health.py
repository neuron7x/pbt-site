#!/usr/bin/env python3
"""Local read-only outbox status. Not /api/health, a worker heartbeat, or an SLO certification.

The operator MUST supply an explicit age threshold; missing/unreadable evidence
is UNKNOWN (exit 2), not HEALTHY. All outputs are aggregates without lead data.
A timestamp up to one second ahead of the sampling clock is tolerated for a
concurrent write between clock sampling and the SQLite snapshot; a greater
offset makes the snapshot unverifiable. The one-second boundary is inclusive.
"""
import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
CLOCK_SKEW_TOLERANCE_S = 1.0


def _age(now, observed):
    if not isinstance(observed, (int, float)) or not math.isfinite(observed):
        raise ValueError('invalid timestamp')
    if not math.isfinite(now) or observed - now > CLOCK_SKEW_TOLERANCE_S:
        raise ValueError('timestamp is in the future')
    return max(0.0, now - observed)


def _display(report):
    """Round only presentation values; policy decisions use the full precision."""
    result = dict(report)
    for key in ('oldest_pending_age_s', 'worker_heartbeat_age_s'):
        if result[key] is not None:
            result[key] = round(result[key], 3)
    return result


def snapshot(path, now):
    if not path.is_file():
        raise OSError('missing database')
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=3)
    try:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        pending, due = db.execute(
            """SELECT count(*),
                      coalesce(sum(CASE WHEN o.next_at <= ? THEN 1 ELSE 0 END), 0)
               FROM outbox o JOIN leads l ON l.id = o.lead_id
               WHERE o.status='pending'""", (now,)).fetchone()
        failed = db.execute("SELECT count(*) FROM outbox WHERE status='failed'").fetchone()[0]
        delivered = db.execute("SELECT count(*) FROM outbox WHERE status='delivered'").fetchone()[0]
        invalid_status = db.execute("SELECT count(*) FROM outbox WHERE status NOT IN ('pending','failed','delivered')").fetchone()[0]
        orphan = db.execute("SELECT count(*) FROM outbox o LEFT JOIN leads l ON l.id=o.lead_id WHERE l.id IS NULL").fetchone()[0]
        has_worker_table = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='runtime_heartbeat'").fetchone()
        worker_at = (db.execute(
            "SELECT observed_at FROM runtime_heartbeat WHERE name='delivery'").fetchone()
                     if has_worker_table else None)
        # SQLite MIN on ISO-8601 text orders local wall times, not instants.
        # Iterate the snapshot without materializing the backlog and verify every
        # timestamp, including rows that are not the oldest.
        age = None
        rows = db.execute("""SELECT l.created, o.next_at FROM outbox o
                             JOIN leads l ON l.id=o.lead_id
                             WHERE o.status='pending'""")
        for value, next_at in rows:
            if not isinstance(next_at, (int, float)) or not math.isfinite(next_at):
                raise ValueError('invalid pending due timestamp')
            if not isinstance(value, str):
                raise ValueError('missing pending timestamp')
            created = datetime.fromisoformat(value)
            if created.utcoffset() is None:
                raise ValueError('pending timestamp has no timezone')
            current_age = _age(now, created.timestamp())
            age = current_age if age is None else max(age, current_age)
        db.execute('ROLLBACK')
        return {'pending': pending, 'due': due, 'failed': failed, 'delivered': delivered,
                'unknown_status_rows': invalid_status, 'orphan_outbox_rows': orphan,
                'oldest_pending_age_s': age,
                'worker_heartbeat_age_s': _age(now, worker_at[0])
                if worker_at else None}
    finally:
        db.close()


def main(argv=None):
    p = argparse.ArgumentParser(description='PBT local, read-only SQLite outbox status')
    p.add_argument('--db', type=Path, default=Path(os.environ.get('LEAD_DB') or ROOT / 'data/leads.db'))
    p.add_argument('--max-pending-age-s', required=True, type=float,
                   help='operator-selected delivery backlog age policy, in seconds')
    p.add_argument('--max-failed', type=int, default=0,
                   help='operator-selected upper bound for permanently failed rows (default 0)')
    p.add_argument('--max-worker-idle-s', type=float, default=None,
                   help='optional explicit policy for observed delivery thread activity')
    a = p.parse_args(argv)
    if (not math.isfinite(a.max_pending_age_s) or a.max_pending_age_s <= 0 or a.max_failed < 0
            or (a.max_worker_idle_s is not None and
                (not math.isfinite(a.max_worker_idle_s) or a.max_worker_idle_s <= 0))):
        print(json.dumps({'ok': False, 'status': 'unknown', 'reason': 'invalid_policy'}))
        return 2
    try:
        report = snapshot(a.db, time.time())
    except (OSError, sqlite3.Error, ValueError, OverflowError) as exc:
        # Do not include paths, payloads, tokens, SQL, contact data or exception messages.
        print(json.dumps({'ok': False, 'status': 'unknown', 'reason': 'storage_unverifiable',
                          'error_type': type(exc).__name__}))
        return 2
    if report['unknown_status_rows'] or report['orphan_outbox_rows']:
        print(json.dumps({'ok': False, 'status': 'unknown', 'reason': 'outbox_integrity', **_display(report)}, sort_keys=True))
        return 2
    if a.max_worker_idle_s is not None and report['worker_heartbeat_age_s'] is None:
        print(json.dumps({'ok': False, 'status': 'unknown', 'reason': 'worker_liveness_unavailable',
                          **_display(report)}, sort_keys=True))
        return 2
    stale = report['oldest_pending_age_s'] is not None and report['oldest_pending_age_s'] > a.max_pending_age_s
    overfailed = report['failed'] > a.max_failed
    stale_worker = (a.max_worker_idle_s is not None and
                    report['worker_heartbeat_age_s'] > a.max_worker_idle_s)
    ok = not stale and not overfailed and not stale_worker
    worker_state = ('not_measured' if a.max_worker_idle_s is None else
                    'stale' if stale_worker else 'recent')
    state = ('degraded' if not ok else
             'idle_or_local_only' if report['pending'] + report['failed'] + report['delivered'] == 0 else 'within_policy')
    print(json.dumps({'ok': ok, 'status': state, 'scope': 'sqlite_outbox_snapshot',
                      'worker_liveness': worker_state, 'production_slo': 'not_verified',
                      'max_pending_age_s': a.max_pending_age_s, 'max_failed': a.max_failed,
                      **_display(report)}, sort_keys=True))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
