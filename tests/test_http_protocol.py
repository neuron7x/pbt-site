"""NET-01/02/05: request framing, media type, proxy identity, process topology.

Raw sockets: http.client would normalize the very framing these tests attack. The protocol is
HTTP/1.0 close-delimited, so each request owns its connection and cannot smuggle a second one.
"""
import fcntl
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest

from test_leads import LEAD, Srv, _port, srv  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
BODY = json.dumps(LEAD).encode()


def raw(srv_obj, headers, body=BODY, timeout=8):
    head = ''.join(f'{k}: {v}\r\n' for k, v in headers)
    data = f'POST /api/lead HTTP/1.1\r\nHost: 127.0.0.1:{srv_obj.port}\r\nOrigin: {srv_obj.base}\r\n{head}\r\n'.encode() + body
    with socket.create_connection(('127.0.0.1', srv_obj.port), timeout=timeout) as s:
        s.sendall(data)
        s.shutdown(socket.SHUT_WR)
        reply = b''
        while chunk := s.recv(4096):
            reply += chunk
    return int(reply.split()[1]) if reply else None


def _count(s):
    with sqlite3.connect(s.db) as c:
        return c.execute('SELECT count(*) FROM leads').fetchone()[0]


@pytest.mark.parametrize('ctype', [
    'text/plain; x=application/json', 'multipart/form-data; boundary=application/json',
    'application/jsonx', 'text/plain, application/json', 'application/json-patch+json',
])
def test_media_type_is_parsed_not_substring_matched(srv, ctype):
    s = srv(DELIVERY_WORKER='0')
    status = raw(s, [('Content-Type', ctype), ('Content-Length', len(BODY))])
    assert status == 415, f'{ctype!r} -> {status}'
    assert _count(s) == 0


@pytest.mark.parametrize('ctype', ['application/json', 'Application/JSON; charset=utf-8', 'application/json ;charset=UTF-8'])
def test_json_media_type_variants_stay_accepted(srv, ctype):
    s = srv(DELIVERY_WORKER='0')
    assert raw(s, [('Content-Type', ctype), ('Content-Length', len(BODY))]) == 201
    assert _count(s) == 1


@pytest.mark.parametrize('length', ['1_0', '+5', '0x10', '-1', '1e2', '٣', '5, 5'])
def test_non_rfc_content_length_is_rejected_without_state(srv, length):
    s = srv(DELIVERY_WORKER='0')
    status = raw(s, [('Content-Type', 'application/json'), ('Content-Length', length)])
    assert status == 400, f'{length!r} -> {status}'
    assert _count(s) == 0


def test_conflicting_duplicate_content_length_is_rejected(srv):
    s = srv(DELIVERY_WORKER='0')
    status = raw(s, [('Content-Type', 'application/json'), ('Content-Length', len(BODY)), ('Content-Length', 5)])
    assert status == 400 and _count(s) == 0


@pytest.mark.parametrize('te', ['chunked', 'gzip, chunked', 'identity'])
def test_transfer_encoding_is_never_accepted_alongside_content_length(srv, te):
    s = srv(DELIVERY_WORKER='0')
    status = raw(s, [('Content-Type', 'application/json'), ('Transfer-Encoding', te), ('Content-Length', len(BODY))])
    assert status == 400 and _count(s) == 0


def test_early_eof_never_accepts_a_truncated_body(srv):
    s = srv(DELIVERY_WORKER='0')
    assert raw(s, [('Content-Type', 'application/json'), ('Content-Length', len(BODY))], BODY[:-3]) == 400
    assert _count(s) == 0


def test_unkeyed_malformed_key_and_json_leave_no_state(srv):
    s = srv(DELIVERY_WORKER='0')
    assert raw(s, [('Content-Type', 'application/json'), ('Content-Length', 5)], b'{"a":') == 400
    assert raw(s, [('Content-Type', 'application/json'), ('Idempotency-Key', 'bad key!'), ('Content-Length', len(BODY))]) == 400
    assert _count(s) == 0


@pytest.mark.parametrize('second_name, second_value', [
    pytest.param('Idempotency-Key', 'k-duplicate-a-0001', id='identical'),
    pytest.param('Idempotency-Key', 'k-duplicate-b-0001', id='conflicting'),
    pytest.param('iDeMpOtEnCy-KeY', 'k-duplicate-a-0001', id='mixed-case-identical'),
    pytest.param('iDeMpOtEnCy-KeY', 'k-duplicate-b-0001', id='mixed-case-conflicting'),
])
def test_duplicate_idempotency_headers_are_rejected_without_state_or_quota(srv, second_name, second_value):
    s = srv(DELIVERY_WORKER='0', RATE_ANY_10MIN='1', RATE_LEAD_10MIN='1', RATE_LEAD_DAY='1',
            LEAD_WEBHOOK_URL='http://127.0.0.1:9/hook', LEAD_WEBHOOK_SECRET='synthetic')
    headers = [('Content-Type', 'application/json'), ('Content-Length', len(BODY)),
               ('Idempotency-Key', 'k-duplicate-a-0001'), (second_name, second_value)]
    assert raw(s, headers) == 400
    assert _count(s) == 0
    assert s.rows('SELECT count(*) FROM outbox') == [(0,)]
    # Even the general request quota remains available; a rejected header
    # cannot reserve either key or charge a lead that was never committed.
    status, accepted, _ = s.post(LEAD, 'k-duplicate-a-0001')
    assert status == 201 and accepted['ref'] == 'PBT-000001'
    assert s.rows('SELECT idem_key FROM leads') == [('k-duplicate-a-0001',)]
    assert s.rows('SELECT count(*) FROM outbox') == [(1,)]


def test_duplicate_idempotency_rejection_closes_without_waiting_for_body(srv):
    s = srv(DELIVERY_WORKER='0', REQUEST_BODY_DEADLINE='5', RATE_ANY_10MIN='1')
    request = (f'POST /api/lead HTTP/1.1\r\nHost: 127.0.0.1:{s.port}\r\nOrigin: {s.base}\r\n'
               f'Content-Type: application/json\r\nContent-Length: {len(BODY)}\r\n'
               'Idempotency-Key: k-no-body-a-0001\r\nIdempotency-Key: k-no-body-b-0001\r\n'
               'Connection: keep-alive\r\n\r\n').encode()
    with socket.create_connection(('127.0.0.1', s.port), timeout=2) as client:
        client.sendall(request)  # Deliberately keep the socket open without a body.
        reply = b''
        while chunk := client.recv(4096):
            reply += chunk
    assert int(reply.split()[1]) == 400
    assert json.loads(reply.partition(b'\r\n\r\n')[2]) == {'ok': False, 'error': 'idempotency_key'}
    assert _count(s) == 0 and s.rows('SELECT count(*) FROM outbox') == [(0,)]
    assert s.post(LEAD, 'k-after-ambiguous-0001')[0] == 201


@pytest.mark.parametrize('key', [None, 'k-single-header-0001'], ids=['absent', 'single'])
def test_single_or_absent_idempotency_header_preserves_lead_contract(srv, key):
    s = srv(DELIVERY_WORKER='0', LEAD_WEBHOOK_URL='http://127.0.0.1:9/hook', LEAD_WEBHOOK_SECRET='synthetic')
    status, accepted, _ = s.post(LEAD, key)
    assert status == 201 and accepted == {'ok': True, 'ref': 'PBT-000001'}
    assert s.rows('SELECT idem_key FROM leads') == [(key,)]
    assert s.rows('SELECT channel, status FROM outbox') == [('webhook', 'pending')]


def test_slow_clients_hold_slots_for_bounded_wall_clock_only(srv):
    """Drip on every slot for the whole test, so per-recv inactivity never fires. Only the absolute
    deadline can free a slot: with REQUEST_TIMEOUT far longer than the bound, nothing else would."""
    s = srv(DELIVERY_WORKER='0', MAX_CONNECTIONS='2', HEADER_TIMEOUT='0.6', REQUEST_TIMEOUT='30', CONN_SLOT_WAIT='3')
    socks = [socket.create_connection(('127.0.0.1', s.port), timeout=5) for _ in range(2)]
    stop = threading.Event()

    def drip():
        while not stop.is_set():
            for sock in socks:
                try:
                    sock.sendall(b'X')
                except OSError:
                    pass
            stop.wait(.1)
    for sock in socks:
        sock.sendall(b'POST /api/lead HTTP/1.1\r\nX-Pad: ')
    thread = threading.Thread(target=drip, daemon=True)
    thread.start()
    try:
        time.sleep(1.2)
        t0 = time.monotonic()
        status = s.post(LEAD, 'k-slot-recovered')[0]
        assert status == 201
        assert time.monotonic() - t0 < 2.5, 'a free slot took longer than the header deadline explains'
    finally:
        stop.set()
        thread.join(2)
        for sock in socks:
            sock.close()
    assert _count(s) == 1


# ─── NET-02: proxy identity ──────────────────────────────
def _keyed(s, key, xff_lines):
    head = [('Content-Type', 'application/json'), ('Idempotency-Key', key), ('Content-Length', len(BODY))]
    return raw(s, head + [('X-Forwarded-For', v) for v in xff_lines])


def test_attacker_first_header_line_cannot_choose_rate_identity(srv):
    """A proxy may append its own header line instead of merging. Only the last value is trusted."""
    s = srv(TRUST_PROXY='1', RATE_LEAD_10MIN='1', RATE_LEAD_DAY='100', DELIVERY_WORKER='0')
    assert _keyed(s, 'k-spoof-000001', ['198.51.100.1', '203.0.113.9']) == 201
    assert _keyed(s, 'k-spoof-000002', ['198.51.100.2', '203.0.113.9']) == 429


def test_untrusted_peer_cannot_set_identity_or_hsts(srv):
    s = srv(TRUST_PROXY='', RATE_LEAD_10MIN='1', RATE_LEAD_DAY='100', DELIVERY_WORKER='0')
    assert _keyed(s, 'k-untrusted-01', ['198.51.100.1']) == 201
    assert _keyed(s, 'k-untrusted-02', ['198.51.100.2']) == 429
    req = (f'GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nX-Forwarded-Proto: https\r\n\r\n').encode()
    with socket.create_connection(('127.0.0.1', s.port), timeout=5) as sock:
        sock.sendall(req)
        head = b''
        while b'\r\n\r\n' not in head:
            head += sock.recv(4096)
    assert b'strict-transport-security' not in head.lower()


# ─── NET-05: single-process topology ─────────────────────
def test_second_server_on_same_database_fails_closed(tmp_path):
    db = tmp_path / 'one.db'
    first = Srv(db, DELIVERY_WORKER='0')
    try:
        env = {'PORT': str(_port()), 'HOST': '127.0.0.1', 'LEAD_DB': str(db), 'DELIVERY_WORKER': '0', 'PATH': '/usr/bin:/bin'}
        second = subprocess.run([sys.executable, str(ROOT / 'server/app.py')], env=env, capture_output=True, text=True, timeout=15)
        assert second.returncode != 0
        assert 'single_process_guard' in second.stderr
        assert first.post(LEAD, 'k-first-alive-1')[0] == 201
    finally:
        first.kill()
    # SIGKILL releases the kernel lock: restart needs no manual cleanup.
    again = Srv(db, DELIVERY_WORKER='0')
    try:
        assert again.post(LEAD, 'k-after-crash-1')[0] == 201
    finally:
        again.kill()


def test_restore_refuses_while_the_guard_is_held_even_on_another_port(tmp_path):
    db = tmp_path / 'held.db'
    live = Srv(db, DELIVERY_WORKER='0')
    try:
        live.post(LEAD, 'k-held-000001')
        snap = tmp_path / 'snap.db'
        with sqlite3.connect(db) as src, sqlite3.connect(snap) as dst:
            src.backup(dst)
        before = db.read_bytes()
        r = subprocess.run([sys.executable, str(ROOT / 'ops/restore.py'), str(snap), '--db', str(db),
                            '--log', str(tmp_path / 'none'), '--min-seq', '1', '--port', '1'],
                           capture_output=True, text=True, timeout=15)
        assert r.returncode == 2 and 'single_process_guard' in r.stderr
        assert db.read_bytes() == before
    finally:
        live.kill()


def test_refused_second_server_writes_nothing_while_restore_or_a_peer_holds_the_guard(tmp_path):
    """Refusal after migrating would still touch a database mid-swap. systemd retries every two seconds."""
    db = tmp_path / 'legacy.db'
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE leads(id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT NOT NULL, type TEXT NOT NULL, payload TEXT NOT NULL, ip_hash TEXT, ua TEXT, delivered TEXT)")
    before = db.read_bytes()
    holder = os.open(f'{db}.server-lock', os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(holder, fcntl.LOCK_EX)
    try:
        env = {'PORT': str(_port()), 'HOST': '127.0.0.1', 'LEAD_DB': str(db), 'PATH': '/usr/bin:/bin'}
        r = subprocess.run([sys.executable, str(ROOT / 'server/app.py')], env=env, capture_output=True, text=True, timeout=15)
    finally:
        os.close(holder)
    assert r.returncode != 0 and 'single_process_guard' in r.stderr
    assert db.read_bytes() == before, 'a refused process wrote schema'
    assert not Path(f'{db}-journal').exists()


def test_unavailable_guard_keeps_static_pages_and_refuses_leads(tmp_path):
    db = tmp_path / 'missing-parent' / 'leads.db'
    s = Srv(db, DELIVERY_WORKER='0')
    try:
        with urllib.request.urlopen(s.base + '/', timeout=5) as page:
            assert page.status == 200
        assert s.post(LEAD, 'k-no-guard-0001')[0] == 503
        try:
            urllib.request.urlopen(s.base + '/api/health', timeout=5)
            assert False, 'health claimed ok without a data directory'
        except urllib.error.HTTPError as e:
            assert e.code == 503
    finally:
        s.kill()
