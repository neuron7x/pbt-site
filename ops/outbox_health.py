#!/usr/bin/env python3
"""Local read-only outbox status. Not /api/health, a worker heartbeat, or an SLO certification.

The operator MUST supply an explicit age threshold; missing/unreadable evidence
is UNKNOWN (exit 2), not HEALTHY. All outputs are aggregates without lead data.
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


def snapshot(path, now):
    if not path.is_file():
        raise OSError('missing database')
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=3)
    try:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        pending, due, oldest = db.execute(
            """SELECT count(*),
                      coalesce(sum(CASE WHEN o.next_at <= ? THEN 1 ELSE 0 END), 0),
                      min(l.created)
               FROM outbox o JOIN leads l ON l.id = o.lead_id
               WHERE o.status='pending'""", (now,)).fetchone()
        failed = db.execute("SELECT count(*) FROM outbox WHERE status='failed'").fetchone()[0]
        delivered = db.execute("SELECT count(*) FROM outbox WHERE status='delivered'").fetchone()[0]
        db.execute('ROLLBACK')
        age = max(0.0, now - datetime.fromisoformat(oldest).timestamp()) if oldest else None
        return {'pending': pending, 'due': due, 'failed': failed, 'delivered': delivered,
                'oldest_pending_age_s': round(age, 3) if age is not None else None}
    finally:
        db.close()


def main(argv=None):
    p = argparse.ArgumentParser(description='PBT local, read-only SQLite outbox status')
    p.add_argument('--db', type=Path, default=Path(os.environ.get('LEAD_DB') or ROOT / 'data/leads.db'))
    p.add_argument('--max-pending-age-s', required=True, type=float,
                   help='operator-selected delivery backlog age policy, in seconds')
    p.add_argument('--max-failed', type=int, default=0,
                   help='operator-selected upper bound for permanently failed rows (default 0)')
    a = p.parse_args(argv)
    if not math.isfinite(a.max_pending_age_s) or a.max_pending_age_s <= 0 or a.max_failed < 0:
        print(json.dumps({'ok': False, 'status': 'unknown', 'reason': 'invalid_policy'}))
        return 2
    try:
        report = snapshot(a.db, time.time())
    except (OSError, sqlite3.Error, ValueError, OverflowError) as exc:
        # Do not include paths, payloads, tokens, SQL, contact data or exception messages.
        print(json.dumps({'ok': False, 'status': 'unknown', 'reason': 'storage_unverifiable',
                          'error_type': type(exc).__name__}))
        return 2
    stale = report['oldest_pending_age_s'] is not None and report['oldest_pending_age_s'] > a.max_pending_age_s
    overfailed = report['failed'] > a.max_failed
    ok = not stale and not overfailed
    state = ('degraded' if not ok else
             'idle_or_local_only' if report['pending'] + report['failed'] + report['delivered'] == 0 else 'within_policy')
    print(json.dumps({'ok': ok, 'status': state, 'scope': 'sqlite_outbox_snapshot',
                      'worker_liveness': 'not_measured', 'production_slo': 'not_verified',
                      'max_pending_age_s': a.max_pending_age_s, 'max_failed': a.max_failed,
                      **report}, sort_keys=True))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
