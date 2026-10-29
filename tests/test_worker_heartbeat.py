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
