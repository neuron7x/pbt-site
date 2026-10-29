"""Adversarial HTTP body framing/deadline tests; no CRM payload changes.

A stalled connection must not retain one of the bounded server worker
slots indefinitely. A truncated but syntactically valid JSON body must
never be accepted as a lead or materialized into the durable outbox.
"""
import json
import select
import socket
import time

from test_leads import LEAD, srv  # noqa: F401 (pytest fixture)


def _request_headers(server, announced_length):
    return (
        f"POST /api/lead HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{server.port}\r\n"
        f"Origin: {server.base}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {announced_length}\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("ascii")


def _read_response(sock):
    data = b""
    while chunk := sock.recv(4096):
        data += chunk
    assert data.startswith(b"HTTP/1."), data[:150]
    return int(data.split(b" ", 2)[1]), data


def test_truncated_but_valid_json_body_is_never_persisted(srv):
    server = srv(REQUEST_TIMEOUT="3")
    payload = json.dumps(LEAD).encode("utf-8")
    with socket.create_connection(("127.0.0.1", server.port), timeout=5) as client:
        client.settimeout(5)
        client.sendall(_request_headers(server, len(payload) + 200) + payload)
        client.shutdown(socket.SHUT_WR)
        status, _ = _read_response(client)
    assert status == 400
    assert server.rows("SELECT count(*) FROM leads") == [(0,)]
    assert server.rows("SELECT count(*) FROM outbox") == [(0,)]


def test_trickle_body_hits_absolute_deadline_despite_frequent_bytes(srv):
    server = srv(REQUEST_BODY_DEADLINE="0.7", REQUEST_TIMEOUT="6")
    with socket.create_connection(("127.0.0.1", server.port), timeout=5) as client:
        client.settimeout(5)
        client.sendall(_request_headers(server, 4096) + b"{")
        started = time.monotonic()
        response = b""
        for _ in range(40):
            readable, _, _ = select.select([client], [], [], 0.1)
            if readable:
                response += client.recv(4096)
                if b"\r\n\r\n" in response:
                    break
            try:
                client.sendall(b" ")
            except OSError:
                break
        elapsed = time.monotonic() - started
    assert response.startswith(b"HTTP/1."), response[:160]
    assert int(response.split(b" ", 2)[1]) == 408, response[:160]
    assert elapsed < 4, f"absolute deadline was not enforced; elapsed={elapsed:.3f}s"
    assert server.rows("SELECT count(*) FROM leads") == [(0,)]
    assert server.rows("SELECT count(*) FROM outbox") == [(0,)]


def test_complete_body_preserves_existing_idempotent_contract(srv):
    server = srv(REQUEST_BODY_DEADLINE="2")
    status, record, _ = server.post(LEAD, key="r1-body-00000001")
    replay_status, replay, _ = server.post(LEAD, key="r1-body-00000001")
    assert status == replay_status == 201
    assert replay["ref"] == record["ref"]
    assert replay["replayed"] is True
    assert server.rows("SELECT count(*) FROM leads") == [(1,)]
