"""NET-01/02/05: request framing, media type, proxy identity, process topology.

Raw sockets: http.client would normalize the very framing these tests attack. The protocol is
HTTP/1.0 close-delimited, so each request owns its connection and cannot smuggle a second one.
"""
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time

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


def test_slow_clients_hold_slots_for_bounded_wall_clock_only(srv):
    """Drip one header byte per interval on every slot. The absolute deadline, not per-recv
    inactivity, must free them: a healthy request then succeeds within a stated bound."""
    s = srv(DELIVERY_WORKER='0', MAX_CONNECTIONS='2', HEADER_TIMEOUT='0.6', REQUEST_TIMEOUT='5', CONN_SLOT_WAIT='5')
    socks = [socket.create_connection(('127.0.0.1', s.port), timeout=5) for _ in range(2)]
    t0 = time.monotonic()
    try:
        for sock in socks:
            sock.sendall(b'POST /api/lead HTTP/1.1\r\n')
        status = None
        while time.monotonic() - t0 < 4:
            for sock in socks:
                try:
                    sock.sendall(b'X')  # Each byte would reset a mere per-recv timeout.
                except OSError:
                    pass
            time.sleep(.1)
            if time.monotonic() - t0 > 1.2:
                status = s.post(LEAD, 'k-slot-recovered')[0]
                break
        assert status == 201
        assert time.monotonic() - t0 < 12
    finally:
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
