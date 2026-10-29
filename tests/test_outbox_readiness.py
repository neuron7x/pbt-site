"""Fail-closed local outbox observability without changing any public HTTP contract."""
from datetime import datetime, timedelta, timezone
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from test_leads import LEAD, srv  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / 'ops' / 'outbox_health.py'


def probe(db, age='600', *opts):
    p = subprocess.run([sys.executable, str(TOOL), '--db', str(db),
                        '--max-pending-age-s', age, *opts],
                       text=True, capture_output=True, timeout=10, check=False)
    assert not p.stderr, p.stderr
    return p.returncode, json.loads(p.stdout)


def test_recent_pending_delivery_is_visible_without_exposing_personal_data(srv):
    server = srv(DELIVERY_WORKER='0', LEAD_WEBHOOK_URL='http://127.0.0.1:9/hook', LEAD_WEBHOOK_SECRET='sec')
    assert server.post(LEAD, 'k-health-000001')[0] == 201
    status, report = probe(server.db)
    assert status == 0 and report['status'] == 'within_policy'
    assert (report['pending'], report['due'], report['failed']) == (1, 1, 0)
    assert report['oldest_pending_age_s'] < 600
    assert report['worker_liveness'] == 'not_measured'
    assert report['production_slo'] == 'not_verified'
    assert all(secret not in json.dumps(report) for secret in ('sec', LEAD['contact'], LEAD['subject']))
    assert server.rows("SELECT count(*) FROM outbox WHERE status='pending'") == [(1,)]


def test_stale_backlog_and_terminal_failure_are_degraded(srv):
    server = srv(DELIVERY_WORKER='0', LEAD_WEBHOOK_URL='http://127.0.0.1:9/hook', LEAD_WEBHOOK_SECRET='sec')
    for i in range(2):
        assert server.post(LEAD, f'k-stale-{i:08d}')[0] == 201
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    with sqlite3.connect(server.db) as db:
        db.execute("UPDATE leads SET created=? WHERE id=1", (old,))
    status, report = probe(server.db)
    assert status == 1 and report['status'] == 'degraded'
    assert report['pending'] == 2 and report['oldest_pending_age_s'] > 600
    with sqlite3.connect(server.db) as db:
        db.execute("UPDATE outbox SET status='failed' WHERE lead_id=1")
    status, report = probe(server.db)
    assert status == 1 and report['failed'] == 1 and report['pending'] == 1
    status, report = probe(server.db, '600', '--max-failed', '1')
    assert status == 0 and report['max_failed'] == 1


def test_empty_local_only_delivery_is_valid_but_not_proof_of_worker_liveness(srv):
    server = srv(DELIVERY_WORKER='0', LEAD_WEBHOOK_URL='', LEAD_WEBHOOK_SECRET='')
    assert server.post(LEAD, 'k-local-only-0001')[0] == 201
    code, report = probe(server.db)
    assert code == 0 and report['status'] == 'idle_or_local_only'
    assert report['worker_liveness'] == 'not_measured'
    assert (report['pending'], report['failed'], report['delivered']) == (0, 0, 0)


def test_missing_database_and_unconfigured_policy_are_not_silent_success(tmp_path):
    db = tmp_path / 'nonexistent.db'
    code, report = probe(db)
    assert code == 2 and report['status'] == 'unknown'
    for threshold in ('0', '-1', 'NaN', 'Infinity'):
        code, report = probe(db, threshold)
        assert code == 2 and report['reason'] == 'invalid_policy'


def test_non_sqlite_database_is_unknown_not_healthy(tmp_path):
    db = tmp_path / 'corrupted.db'
    db.write_bytes(b'not a sqlite file')
    code, report = probe(db)
    assert code == 2 and report['status'] == 'unknown'
    assert report['reason'] == 'storage_unverifiable'
