"""NET-04 / INV-03: accepted, attempted, retried, acknowledged and terminal are distinct durable states.

The receiver here is a synthetic in-process stub with a dedup store. It proves the site's retry and
identity behavior against such a receiver; it proves nothing about the real CRM.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time

import pytest

from test_data_integrity import _post, _server_process
from test_leads import LEAD, _port, srv  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
SECRET = 'synthetic-secret'


class Receiver:
    """Scripted receiver: statuses[n] answers the nth attempt; verified bodies are deduplicated by id."""

    def __init__(self, statuses=(200,), delay=0):
        self.statuses, self.delay = list(statuses), delay
        self.attempts, self.persisted, self.bad_hmac = [], {}, 0
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers['Content-Length']))
                expected = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
                if not hmac.compare_digest(expected, self.headers.get('X-PBT-Signature', '')):
                    outer.bad_hmac += 1
                lead = json.loads(body)
                index = len(outer.attempts)
                outer.attempts.append(lead['id'])
                status = outer.statuses[min(index, len(outer.statuses) - 1)]
                if outer.delay and index == 0:
                    time.sleep(outer.delay)
                if 200 <= status < 300:
                    outer.persisted[lead['id']] = lead
                self.send_response(status)
                self.send_header('Content-Length', '0')
                self.end_headers()

            def log_message(self, *a):
                pass
        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f'http://127.0.0.1:{self.httpd.server_address[1]}/hook'

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def _row(s):
    return s.rows("SELECT status, attempts, last_error, delivered_at IS NOT NULL FROM outbox")[0]


def _wait(s, predicate, seconds=15):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        rows = s.rows('SELECT status FROM outbox')
        if rows and predicate(rows[0][0]):
            return
        time.sleep(.05)
    pytest.fail(f'timeout; rows={s.rows("SELECT status, attempts, last_error FROM outbox")}')


@pytest.mark.parametrize('fault', [408, 429, 500, 503])
def test_transient_status_is_retried_to_acknowledgement(srv, fault):
    r = Receiver([fault, fault, 200])
    try:
        s = srv(LEAD_WEBHOOK_URL=r.url, LEAD_WEBHOOK_SECRET=SECRET)
        assert s.post(LEAD, f'k-transient-{fault}')[0] == 201
        _wait(s, lambda st: st == 'delivered')
        assert _row(s) == ('delivered', 3, None, 1)
        assert r.attempts == [1, 1, 1] and r.bad_hmac == 0
    finally:
        r.close()


@pytest.mark.parametrize('fault', [400, 403, 404, 410, 422])
def test_permanent_status_is_terminal_with_exactly_one_attempt(srv, fault):
    r = Receiver([fault])
    try:
        s = srv(LEAD_WEBHOOK_URL=r.url, LEAD_WEBHOOK_SECRET=SECRET)
        assert s.post(LEAD, f'k-permanent-{fault}')[0] == 201
        _wait(s, lambda st: st == 'failed')
        time.sleep(.3)
        assert _row(s) == ('failed', 1, f'HTTP {fault}', 0)
        assert r.attempts == [1] and r.persisted == {}
        assert s.rows('SELECT count(*) FROM leads') == [(1,)]  # The accepted lead is never lost.
    finally:
        r.close()


def test_retry_budget_exhaustion_is_an_explicit_terminal_state(srv):
    r = Receiver([503])
    try:
        s = srv(LEAD_WEBHOOK_URL=r.url, LEAD_WEBHOOK_SECRET=SECRET, DELIVERY_MAX_ATTEMPTS='3')
        assert s.post(LEAD, 'k-exhausted-001')[0] == 201
        _wait(s, lambda st: st == 'failed')
        assert _row(s) == ('failed', 3, 'HTTP 503', 0)
        assert len(r.attempts) == 3
    finally:
        r.close()


def test_slow_receiver_times_out_then_retry_carries_same_identity(srv):
    r = Receiver([200], delay=3)
    try:
        s = srv(LEAD_WEBHOOK_URL=r.url, LEAD_WEBHOOK_SECRET=SECRET, DELIVERY_TIMEOUT='0.5')
        assert s.post(LEAD, 'k-slow-recv-001')[0] == 201
        _wait(s, lambda st: st == 'delivered')
        assert set(r.attempts) == {1} and len(r.attempts) >= 2  # At-least-once: receiver saw it twice.
        assert list(r.persisted) == [1]
    finally:
        r.close()


def test_death_after_remote_ack_redelivers_same_id_after_restart(tmp_path):
    """At-least-once in its pure form. The receiver has it; the site does not know. Then reconcile."""
    r = Receiver([200])
    db = tmp_path / 'ack.db'
    hook = {'LEAD_WEBHOOK_URL': r.url, 'LEAD_WEBHOOK_SECRET': SECRET, 'DELIVERY_WORKER': '1',
            'DELIVERY_POLL_S': '0.05', 'DELIVERY_BACKOFF_S': '0.05'}
    try:
        port = _port()
        p = _server_process(db, port, PBT_CUT='after_remote_ack', **hook)
        assert _post(port, LEAD, 'k-after-ack-001')[0] == 201
        assert p.wait(15) == -9
        assert r.attempts == [1]
        with sqlite3.connect(db) as c:
            assert c.execute('SELECT status, attempts FROM outbox').fetchall() == [('pending', 0)]
        port2 = _port()
        p2 = _server_process(db, port2, **hook)
        try:
            end = time.monotonic() + 15
            while time.monotonic() < end:
                with sqlite3.connect(db) as c:
                    if c.execute('SELECT status FROM outbox').fetchone()[0] == 'delivered':
                        break
                time.sleep(.05)
        finally:
            p2.kill(); p2.wait(5)
        assert r.attempts == [1, 1], 'same logical id must be redelivered, never a new id'
        with sqlite3.connect(db) as c:
            accepted = {x for (x,) in c.execute('SELECT id FROM leads')}
            acked = {x for (x,) in c.execute("SELECT lead_id FROM outbox WHERE status='delivered'")}
        assert accepted == acked == set(r.persisted) == {1}
    finally:
        r.close()


def test_outbox_health_names_transport_ack_and_not_receipt(srv):
    r = Receiver([200])
    try:
        s = srv(LEAD_WEBHOOK_URL=r.url, LEAD_WEBHOOK_SECRET=SECRET)
        assert s.post(LEAD, 'k-health-name-1')[0] == 201
        _wait(s, lambda st: st == 'delivered')
        out = subprocess.run([sys.executable, str(ROOT / 'ops/outbox_health.py'), '--db', str(s.db),
                              '--max-pending-age-s', '60'], capture_output=True, text=True, timeout=15)
        report = json.loads(out.stdout)
        assert report['delivered'] == 1
        assert report['delivered_evidence'] == 'transport_2xx_only'
        assert report['receiver_persistence'] == 'not_verified'
    finally:
        r.close()
