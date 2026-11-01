#!/usr/bin/env python3
"""Readiness truth table: each signal claims only what was observed, in aggregate, without lead data.

/api/health stays what it was (process answers, SQLite writable, disk free). This separates what that
is routinely mistaken for. A signal is PASS only on direct observation; absence of evidence is UNKNOWN.

  storage_snapshot            SQLite snapshot readable and outbox rows structurally valid
  worker_activity             delivery thread recorded activity within policy. Says nothing about delivery
  delivery_backlog            oldest pending row is within the operator's age policy
  delivery_terminal_failures  terminal rows within the operator's bound
  transport_ack               at least one receiver returned 2xx. Transport event only
  receiver_persistence        an external receipt names every acknowledged lead id
  business_processing         no mechanism observes this: always UNKNOWN

Exit: 0 all PASS; 1 any FAIL; 2 no FAIL but something UNKNOWN. The thresholds are operator input,
not an adopted SLO. A receipt file is only as authentic as its source; its provenance is not checked here.
"""
import argparse
import json
import math
import os
from pathlib import Path
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import outbox_health  # noqa: E402

RECEIPT_SCHEMA = 'pbt-receiver-receipt-v1'


def _receipt_signal(path, acknowledged):
    if path is None:
        return 'UNKNOWN', None
    try:
        receipt = json.loads(path.read_text(encoding='utf-8'))
        if receipt['schema'] != RECEIPT_SCHEMA or not receipt['receipt_id'] or not receipt['receiver']:
            return 'UNKNOWN', None
        persisted = receipt['persisted_lead_ids']
        if not isinstance(persisted, list) or not all(type(x) is int for x in persisted):
            return 'UNKNOWN', None
    except (OSError, ValueError, KeyError, TypeError):
        return 'UNKNOWN', None
    if not acknowledged:
        return 'UNKNOWN', receipt['receipt_id']
    return ('PASS' if acknowledged <= set(persisted) else 'FAIL'), receipt['receipt_id']


def evaluate(db_path, now, max_pending_age_s, max_failed, max_worker_idle_s, receipt_path=None):
    signals = dict.fromkeys(('storage_snapshot', 'worker_activity', 'delivery_backlog',
                             'delivery_terminal_failures', 'transport_ack', 'receiver_persistence',
                             'business_processing'), 'UNKNOWN')
    aggregates, receipt_id = {}, None
    try:
        report = outbox_health.snapshot(db_path, now)
        with sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True, timeout=3) as db:
            acknowledged = {r[0] for r in db.execute("SELECT lead_id FROM outbox WHERE status='delivered'")}
    except (OSError, sqlite3.Error, ValueError, OverflowError) as exc:
        return signals, {'error_type': type(exc).__name__}, None
    aggregates = {k: report[k] for k in ('pending', 'due', 'failed', 'delivered', 'oldest_pending_age_s',
                                         'worker_heartbeat_age_s', 'orphan_outbox_rows', 'unknown_status_rows')}
    signals['storage_snapshot'] = 'FAIL' if report['orphan_outbox_rows'] or report['unknown_status_rows'] else 'PASS'
    heartbeat = report['worker_heartbeat_age_s']
    if heartbeat is not None:
        signals['worker_activity'] = 'PASS' if heartbeat <= max_worker_idle_s else 'FAIL'
    oldest = report['oldest_pending_age_s']
    signals['delivery_backlog'] = 'FAIL' if oldest is not None and oldest > max_pending_age_s else 'PASS'
    signals['delivery_terminal_failures'] = 'FAIL' if report['failed'] > max_failed else 'PASS'
    if report['delivered']:
        signals['transport_ack'] = 'PASS'
    signals['receiver_persistence'], receipt_id = _receipt_signal(receipt_path, acknowledged)
    return signals, aggregates, receipt_id


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--db', type=Path, default=Path(os.environ.get('LEAD_DB') or outbox_health.ROOT / 'data/leads.db'))
    p.add_argument('--max-pending-age-s', required=True, type=float)
    p.add_argument('--max-failed', type=int, default=0)
    p.add_argument('--max-worker-idle-s', required=True, type=float)
    p.add_argument('--receiver-receipt', type=Path, default=None)
    a = p.parse_args(argv)
    if (not math.isfinite(a.max_pending_age_s) or a.max_pending_age_s <= 0 or a.max_failed < 0
            or not math.isfinite(a.max_worker_idle_s) or a.max_worker_idle_s <= 0):
        print(json.dumps({'ready': False, 'reason': 'invalid_policy'}))
        return 2
    signals, aggregates, receipt_id = evaluate(a.db, time.time(), a.max_pending_age_s, a.max_failed,
                                               a.max_worker_idle_s, a.receiver_receipt)
    ready = all(v == 'PASS' for v in signals.values())
    print(json.dumps({'ready': ready, 'signals': signals, 'aggregates': aggregates, 'receipt_id': receipt_id,
                      'production_slo': 'not_verified', 'scope': 'local_sqlite_snapshot_plus_supplied_receipt'},
                     sort_keys=True))
    if 'FAIL' in signals.values():
        return 1
    return 0 if ready else 2


if __name__ == '__main__':
    sys.exit(main())
