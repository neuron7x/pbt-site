"""Absolute outbound HTTP deadline, stalled 51-lead backlog and no orphan child."""
import hashlib
import hmac
import json
import os
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from test_leads import LEAD, srv, wait_for  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
CHILD = ROOT / 'server' / 'delivery_transport.py'


def trickle_receiver():
    """Deliberately never end the status-header line; 2xx body test is separate."""
    fast = threading.Event()
    seen = []
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get('Content-Length') or 0))
            with lock:
                seen.append((raw, self.headers.get('X-PBT-Signature')))
            if fast.is_set():
                self.send_response(200)
                self.send_header('Content-Length', '2')
                self.end_headers()
                self.wfile.write(b'{}')
                return
            try:
                self.wfile.write(b'HTTP/1.1 200 OK\r\nX-Drip: ')
                self.wfile.flush()
                for _ in range(100):
                    self.wfile.write(b'a')
                    self.wfile.flush()
                    time.sleep(.07)
                self.wfile.write(b'\r\n\r\n')
                self.wfile.flush()
            except OSError:
                pass  # A killed child closes its connection.

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, t, fast, seen, f'http://127.0.0.1:{server.server_address[1]}/hook'


def test_one_slow_header_is_bounded_without_weakening_hmac_or_retries(srv):
    receiver, thread, fast, seen, url = trickle_receiver()
    try:
        site = srv(LEAD_WEBHOOK_URL=url, LEAD_WEBHOOK_SECRET='sec',
                   DELIVERY_TIMEOUT='.4', DELIVERY_MAX_ATTEMPTS='3',
                   DELIVERY_BACKOFF_S='30', DELIVERY_POLL_S='30')
        start = time.monotonic()
        assert site.post(LEAD, 'k-header-00001')[0] == 201
        row = wait_for(lambda: [r for r in site.rows(
            'SELECT status, attempts, last_error FROM outbox') if r[1] >= 1], timeout=3)
        assert row == [('pending', 1, 'outbound_total_deadline')], row
        assert time.monotonic() - start < 2.5, 'header trickle bypassed total deadline'
        assert site.rows('SELECT count(*) FROM leads') == [(1,)]
        assert len(seen) == 1
        assert hmac.compare_digest(seen[0][1], hmac.new(b'sec', seen[0][0], hashlib.sha256).hexdigest())
    finally:
        receiver.shutdown()
        receiver.server_close()
        thread.join(timeout=3)


def test_51_saturated_header_stalls_then_restart_drains_without_loss(srv):
    """No per-socket trickle can indefinitely occupy the four outbound slots."""
    receiver, thread, fast, seen, url = trickle_receiver()
    try:
        site = srv(DELIVERY_WORKER='0', LEAD_WEBHOOK_URL=url, LEAD_WEBHOOK_SECRET='sec')
        for i in range(51):
            assert site.post(LEAD, f'k-saturation-{i:05d}')[0] == 201
        assert site.rows("SELECT count(*) FROM outbox WHERE status='pending'") == [(51,)]
        site.kill()
        start = time.monotonic()
        stalled = srv(LEAD_WEBHOOK_URL=url, LEAD_WEBHOOK_SECRET='sec',
                      DELIVERY_CONCURRENCY='4', DELIVERY_TIMEOUT='.4',
                      DELIVERY_POLL_S='30', DELIVERY_BACKOFF_S='30')
        attempts = wait_for(lambda: stalled.rows(
            'SELECT count(*) FROM outbox WHERE attempts=1') == [(51,)] or None, timeout=16)
        elapsed = time.monotonic() - start
        assert attempts and elapsed < 16, f'51 stalled slots unbounded: {elapsed}'
        assert stalled.rows("SELECT count(*) FROM outbox WHERE status='pending'") == [(51,)]
        assert stalled.rows("SELECT count(*) FROM outbox WHERE status='failed'") == [(0,)]
        stalled.kill()
        fast.set()
        with sqlite3.connect(site.db) as db:
            db.execute("UPDATE outbox SET next_at=0 WHERE status='pending'")
        recovered = srv(LEAD_WEBHOOK_URL=url, LEAD_WEBHOOK_SECRET='sec',
                        DELIVERY_POLL_S='.05', DELIVERY_CONCURRENCY='4', DELIVERY_TIMEOUT='2')
        delivered = wait_for(lambda: recovered.rows(
            "SELECT count(*) FROM outbox WHERE status='delivered'") == [(51,)] or None, timeout=15)
        assert delivered, 'accepted leads failed to drain after restart'
        assert recovered.rows('SELECT sum(attempts),count(*) FROM outbox') == [(102, 51)]
        assert recovered.rows("SELECT count(*) FROM outbox WHERE status='failed'") == [(0,)]
        assert recovered.rows('SELECT count(*) FROM leads') == [(51,)]
        # A killed child can time out before transmitting its request at all.
        # Only *received* bodies are HMAC-checked; all 51 recovered deliveries
        # must have been observed, without pretending every aborted try arrived.
        assert len(seen) >= 51
        assert sorted({json.loads(raw)['id'] for raw, _ in seen}) == list(range(1, 52))
        for raw, sig in seen:
            assert hmac.compare_digest(sig, hmac.new(b'sec', raw, hashlib.sha256).hexdigest())
    finally:
        receiver.shutdown()
        receiver.server_close()
        thread.join(timeout=3)


def test_child_refuses_wrong_parent_and_no_stdin_payload_is_logged():
    env = dict(os.environ, PBT_PARENT_PID='1')
    p = subprocess.run([sys.executable, str(CHILD)], input=b'{}',
                       capture_output=True, env=env, timeout=4)
    assert p.returncode == 12 and not p.stdout and not p.stderr


def test_unsupported_total_deadline_configuration_fails_closed(tmp_path):
    for value in ('nan', 'inf', '0', '-1', '10000'):
        env = dict(os.environ, HOST='127.0.0.1', PORT='0',
                   LEAD_DB=str(tmp_path / 'missing.db'), DELIVERY_TIMEOUT=value,
                   PYTHONDONTWRITEBYTECODE='1')
        p = subprocess.run([sys.executable, str(ROOT / 'server' / 'app.py')],
                           env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                           timeout=4, check=False)
        assert p.returncode != 0, value


def test_redirect_does_not_forward_webhook_hmac_to_other_host(srv):
    """A signed request must not leak to a redirect target, even on 307."""
    from test_leads import Stub

    destination = Stub()
    captured = []

    class Redirect(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get('Content-Length') or 0))
            captured.append((body, self.headers.get('X-PBT-Signature')))
            self.send_response(307)
            self.send_header('Location', destination.url + '/forwarded')
            self.send_header('Content-Length', '0')
            self.end_headers()

        def log_message(self, *args):
            pass

    sender = ThreadingHTTPServer(('127.0.0.1', 0), Redirect)
    sender.daemon_threads = True
    t = threading.Thread(target=sender.serve_forever, daemon=True)
    t.start()
    try:
        site = srv(LEAD_WEBHOOK_URL=f'http://127.0.0.1:{sender.server_address[1]}/hook',
                   LEAD_WEBHOOK_SECRET='sec', DELIVERY_MAX_ATTEMPTS='1')
        assert site.post(LEAD, 'k-redirect-001')[0] == 201
        assert wait_for(lambda: site.rows(
            "SELECT count(*) FROM outbox WHERE status='failed'") == [(1,)] or None, timeout=5)
        assert destination.hits == []
        assert len(captured) == 1
        raw, sig = captured[0]
        assert hmac.compare_digest(sig, hmac.new(b'sec', raw, hashlib.sha256).hexdigest())
        assert site.rows('SELECT count(*) FROM leads') == [(1,)]
    finally:
        sender.shutdown()
        sender.server_close()
        t.join(timeout=3)
        destination.close()


@pytest.mark.parametrize(('key', 'value'), [
    ('HEADER_TIMEOUT', 'nan'), ('HEADER_TIMEOUT', 'inf'), ('HEADER_TIMEOUT', '-1'),
    ('REQUEST_TIMEOUT', 'nan'), ('REQUEST_TIMEOUT', '-1'),
    ('DELIVERY_MAX_ATTEMPTS', '-1'), ('DELIVERY_MAX_ATTEMPTS', '1000000'),
    ('DELIVERY_BACKOFF_S', 'nan'), ('DELIVERY_BACKOFF_S', '-1'),
    ('DELIVERY_POLL_S', 'nan'), ('DELIVERY_POLL_S', '0'),
    ('HEALTH_MIN_FREE_MB', 'nan'), ('HEALTH_MIN_FREE_MB', '-1'),
    ('CONN_SLOT_WAIT', 'nan'), ('CONN_SLOT_WAIT', '-1'),
])
def test_invalid_operational_timeout_and_retry_configuration_fails_closed(tmp_path, key, value):
    """Never accept non-finite deadlines or retries that silently kill liveness."""
    env = dict(os.environ, HOST='127.0.0.1', PORT='0',
               LEAD_DB=str(tmp_path / 'missing.db'), PYTHONDONTWRITEBYTECODE='1')
    env[key] = value
    result = subprocess.run([sys.executable, str(ROOT / 'server' / 'app.py')],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            timeout=4, check=False)
    assert result.returncode != 0, (key, value)
    assert key.encode() in result.stderr, (key, value, result.stderr[-600:])


def test_sigkill_parent_kills_inflight_delivery_child(srv):
    """A killed server must not leave a live orphan sender holding PII/HMAC."""
    if sys.platform != 'linux':
        pytest.skip('PR_SET_PDEATHSIG requires Linux')
    from tools.runtime_soak import _descendants

    receiver, thread, fast, seen, url = trickle_receiver()
    try:
        site = srv(LEAD_WEBHOOK_URL=url, LEAD_WEBHOOK_SECRET='sec',
                   DELIVERY_TIMEOUT='3', DELIVERY_POLL_S='.05')
        assert site.post(LEAD, 'k-pdeath-000001')[0] == 201
        child_pid = wait_for(
            lambda: next(iter(_descendants(site.p.pid)), None), timeout=2)
        assert child_pid is not None, 'an active delivery child was never observed'

        def still_running(pid):
            try:
                status = Path(f'/proc/{pid}/status').read_text()
            except FileNotFoundError:
                return False
            state = next((row.split()[1] for row in status.splitlines()
                          if row.startswith('State:')), '?')
            return state != 'Z'

        assert still_running(child_pid), 'sender exited before crash injection'
        site.kill(hard=True)
        stopped = wait_for(lambda: not still_running(child_pid) or None, timeout=4)
        assert stopped, 'PR_SET_PDEATHSIG failed to terminate orphan delivery'
        assert site.rows('SELECT count(*) FROM leads') == [(1,)]
        assert site.rows("SELECT count(*) FROM outbox WHERE status='pending'") == [(1,)]
    finally:
        receiver.shutdown()
        receiver.server_close()
        thread.join(timeout=3)


@pytest.mark.parametrize(('key', 'url'), [
    ('LEAD_WEBHOOK_URL', 'http://192.0.2.19/hook'),
    ('LEAD_WEBHOOK_URL', 'http://example.invalid/hook'),
    ('LEAD_WEBHOOK_URL', 'https://user:password@example.invalid/hook'),
    ('TELEGRAM_API_BASE', 'http://198.51.100.9/api'),
    ('TELEGRAM_API_BASE', 'file:///tmp/unsafe'),
])
def test_remote_plaintext_or_uri_credentials_fail_at_startup(tmp_path, key, url):
    """HMAC integrity never substitutes for confidentiality of lead contact data."""
    env = dict(os.environ, HOST='127.0.0.1', PORT='0',
               LEAD_DB=str(tmp_path / 'leads.db'), PYTHONDONTWRITEBYTECODE='1')
    env[key] = url
    p = subprocess.run([sys.executable, str(ROOT / 'server' / 'app.py')],
                       capture_output=True, timeout=4, env=env, check=False)
    assert p.returncode != 0, (key, url)
    assert b'insecure outbound delivery URL' in p.stderr


@pytest.mark.parametrize('url', [
    'http://192.0.2.19/hook', 'http://example.invalid/hook',
    'file:///tmp/unsafe', 'https://token:password@example.invalid/api',
])
def test_child_fails_closed_without_contacting_plaintext_remote(url):
    """Defense in depth: a direct child invocation also refuses insecure URLs."""
    import base64
    envelope = json.dumps({
        'url': url, 'headers': {'Content-Type': 'application/json'},
        'body_b64': base64.b64encode(b'{"id":1}').decode(),
        'socket_timeout_s': 1,
    }).encode()
    env = dict(os.environ, PBT_PARENT_PID=str(os.getpid()))
    p = subprocess.run([sys.executable, str(CHILD)], input=envelope,
                       capture_output=True, timeout=3, env=env, check=False)
    assert p.returncode == 12, (url, p.stdout, p.stderr)
    assert not p.stdout and not p.stderr
