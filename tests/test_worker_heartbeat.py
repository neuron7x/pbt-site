"""Optional local worker-liveness check; no public /api/health changes."""
import json
import sqlite3
import time

from test_leads import srv, wait_for  # noqa: F401
from test_outbox_readiness import probe


def test_heartbeat_exists_for_real_worker_and_is_optional(srv):
    server = srv(DELIVERY_WORKER='1', LEAD_WEBHOOK_URL='',
                 DELIVERY_HEARTBEAT_INTERVAL_S='1', DELIVERY_POLL_S='.1')
    assert wait_for(lambda: server.rows(
        "SELECT count(*) FROM runtime_heartbeat WHERE name='delivery'") == [(1,)] or None, timeout=4)
    code, report = probe(server.db, '600', '--max-worker-idle-s', '5')
    assert code == 0, report
    assert report['status'] == 'idle_or_local_only'
    assert report['worker_liveness'] == 'recent'
    assert report['worker_heartbeat_age_s'] <= 5
    code, default = probe(server.db)
    assert code == 0 and default['worker_liveness'] == 'not_measured'


def test_disabled_worker_is_unknown_when_liveness_required(srv):
    server = srv(DELIVERY_WORKER='0', LEAD_WEBHOOK_URL='')
    code, report = probe(server.db, '600', '--max-worker-idle-s', '5')
    assert code == 2 and report['status'] == 'unknown'
    assert report['reason'] == 'worker_liveness_unavailable'


def test_stale_worker_heartbeat_is_degraded_after_process_exit(srv):
    server = srv(DELIVERY_WORKER='1', LEAD_WEBHOOK_URL='',
                 DELIVERY_HEARTBEAT_INTERVAL_S='1', DELIVERY_POLL_S='30')
    assert wait_for(lambda: server.rows("SELECT count(*) FROM runtime_heartbeat") == [(1,)] or None)
    server.kill()
    with sqlite3.connect(server.db) as db:
        db.execute("UPDATE runtime_heartbeat SET observed_at=? WHERE name='delivery'", (time.time() - 120,))
    code, report = probe(server.db, '600', '--max-worker-idle-s', '5')
    assert code == 1 and report['status'] == 'degraded'
    assert report['worker_liveness'] == 'stale'
    assert report['worker_heartbeat_age_s'] > 5


def test_invalid_liveness_threshold_is_never_silently_accepted(srv):
    server = srv(DELIVERY_WORKER='0', LEAD_WEBHOOK_URL='')
    for threshold in ('0', '-2', 'NaN', 'Infinity'):
        code, report = probe(server.db, '600', '--max-worker-idle-s', threshold)
        assert code == 2 and report['reason'] == 'invalid_policy'


def test_heartbeat_advances_during_stalled_51_row_batch(tmp_path):
    """Real SQLite/worker integration: heartbeat must advance before slow send completes.

    Uses a controllable in-process outbound fake, not an actual CRM receipt.
    All 51 durable outbox rows must drain after releasing the stalled send.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    script = r'''
import importlib.util, json, sqlite3, subprocess, sys, threading, time
from datetime import datetime, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location('pbt_heartbeat_backlog_probe', Path('server/app.py'))
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
assert app._schema_ok.is_set()
app.DELIVERY_HEARTBEAT_INTERVAL_S = 1
app.DELIVERY_POLL_S = 0.1
app.DELIVERY_CONCURRENCY = 4

with sqlite3.connect(app.DB) as conn:
    for i in range(51):
        lead = conn.execute(
            "INSERT INTO leads(created,type,payload) VALUES(?,?,?)",
            (datetime.now(timezone.utc).isoformat(), 'rent', '{"type":"rent"}')
        ).lastrowid
        conn.execute("INSERT INTO outbox(lead_id,channel) VALUES(?,?)", (lead, 'webhook'))

entered, release = threading.Event(), threading.Event()

def stubbed_outbound(row):
    if row[0] == 1:
        entered.set()
        release.wait(timeout=8)
    return None, False

app._attempt_delivery = stubbed_outbound
worker = threading.Thread(target=app.delivery_worker, name='probe-delivery', daemon=True)
worker.start()
try:
    assert entered.wait(timeout=3), 'the first batch never started'
    with sqlite3.connect(app.DB) as conn:
        first = conn.execute(
            "SELECT observed_at FROM runtime_heartbeat WHERE name='delivery'"
        ).fetchone()
    assert first and first[0] > 0, first
    end = time.monotonic() + 4.5
    new = first[0]
    while time.monotonic() < end and new <= first[0] + 0.5:
        time.sleep(0.05)
        with sqlite3.connect(app.DB) as conn:
            row = conn.execute(
                "SELECT observed_at FROM runtime_heartbeat WHERE name='delivery'"
            ).fetchone()
        new = row[0] if row else 0
    assert new > first[0] + 0.5, 'worker heartbeat stalled while network futures were in flight'
    assert not release.is_set(), 'test did not observe heartbeat during the stalled send'
    health = subprocess.run(
        [sys.executable, 'ops/outbox_health.py', '--db', str(app.DB),
         '--max-pending-age-s', '600', '--max-worker-idle-s', '3'],
        capture_output=True, text=True, timeout=4, check=False)
    assert health.returncode == 0, (health.stdout, health.stderr)
    report = json.loads(health.stdout)
    assert report['worker_liveness'] == 'recent', report
finally:
    release.set()

end = time.monotonic() + 5
while time.monotonic() < end:
    with sqlite3.connect(app.DB) as conn:
        pending = conn.execute("SELECT count(*) FROM outbox WHERE status='pending'").fetchone()[0]
        failed = conn.execute("SELECT count(*) FROM outbox WHERE status='failed'").fetchone()[0]
    if pending == 0:
        break
    time.sleep(0.05)
assert pending == failed == 0, (pending, failed)
print(json.dumps({'rows':51,'heartbeat_advanced_during_stall':True,
                  'remaining_pending':pending,'failed':failed}))
'''
    env = {**os.environ, 'LEAD_DB': str(tmp_path / 'heartbeat-backlog.db'),
           'IP_HASH_SALT': 'heartbeat-test-isolated', 'DELIVERY_WORKER': '0',
           'LEAD_WEBHOOK_URL': '', 'TELEGRAM_BOT_TOKEN': '',
           'TELEGRAM_CHAT_ID': '', 'PYTHONDONTWRITEBYTECODE': '1'}
    run = subprocess.run([sys.executable, '-c', script], cwd=root, env=env,
                         capture_output=True, text=True, timeout=17, check=False)
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout.strip().splitlines()[-1])
    assert result['rows'] == 51 and result['heartbeat_advanced_during_stall']
    assert result['remaining_pending'] == result['failed'] == 0
