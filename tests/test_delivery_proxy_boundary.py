"""Plaintext loopback delivery stays local even with inherited proxy settings."""
import hashlib
import hmac
import json

import pytest

from test_leads import LEAD, Stub, srv, wait_for  # noqa: F401


def proxy_environment(url):
    return {'HTTP_PROXY': url, 'http_proxy': url, 'HTTPS_PROXY': url, 'https_proxy': url,
            'ALL_PROXY': '', 'all_proxy': '', 'NO_PROXY': '', 'no_proxy': ''}


@pytest.mark.parametrize('channel', ['webhook', 'telegram'])
def test_loopback_http_delivery_bypasses_environment_proxy(srv, channel):
    receiver, proxy = Stub(), Stub()
    try:
        env = proxy_environment(proxy.url)
        if channel == 'webhook':
            env.update(LEAD_WEBHOOK_URL=receiver.url + '/hook', LEAD_WEBHOOK_SECRET='synthetic-secret')
        else:
            env.update(TELEGRAM_API_BASE=receiver.url, TELEGRAM_BOT_TOKEN='123:abc', TELEGRAM_CHAT_ID='42')
        site = srv(**env)
        status, accepted, _ = site.post(LEAD, 'k-loopback-proxy-0001')
        assert status == 201 and accepted['ref'] == 'PBT-000001'
        assert wait_for(lambda: site.rows('SELECT status, attempts FROM outbox') == [('delivered', 1)])
        # Keep assertion artifacts free of request bodies and signature values.
        proxy_count, receiver_count = len(proxy.hits), len(receiver.hits)
        assert proxy_count == 0
        assert receiver_count == 1
        path, raw, headers = receiver.hits[0]
        message = json.loads(raw)
        if channel == 'webhook':
            assert path == '/hook' and message['id'] == 1
            headers = {key.lower(): value for key, value in headers.items()}
            valid_signature = hmac.compare_digest(
                headers.get('x-pbt-signature', ''), hmac.new(b'synthetic-secret', raw, hashlib.sha256).hexdigest())
            assert valid_signature
        else:
            assert path == '/bot123:abc/sendMessage' and message['chat_id'] == '42'
        assert site.rows('SELECT count(*) FROM leads') == [(1,)]
    finally:
        for stub in (receiver, proxy):
            stub.close()
            stub.srv.server_close()


def test_https_delivery_still_uses_configured_proxy(srv, monkeypatch):
    """A synthetic CONNECT refusal proves HTTPS proxy routing without external TLS."""
    receiver, proxy = Stub(), Stub()
    tunnels = []

    def reject_tunnel(handler):
        tunnels.append(handler.path)
        handler.send_response(502)
        handler.send_header('Content-Length', '0')
        handler.end_headers()

    monkeypatch.setattr(proxy.srv.RequestHandlerClass, 'do_CONNECT', reject_tunnel, raising=False)
    try:
        site = srv(**proxy_environment(proxy.url),
                   LEAD_WEBHOOK_URL=receiver.url.replace('http:', 'https:', 1) + '/hook',
                   LEAD_WEBHOOK_SECRET='synthetic-secret', DELIVERY_MAX_ATTEMPTS='1')
        assert site.post(LEAD, 'k-https-proxy-0001')[0] == 201
        assert wait_for(lambda: site.rows('SELECT status, attempts FROM outbox') == [('failed', 1)])
        assert tunnels == [receiver.url.removeprefix('http://')]
        proxy_count, receiver_count = len(proxy.hits), len(receiver.hits)
        assert proxy_count == receiver_count == 0
        assert site.rows('SELECT count(*) FROM leads') == [(1,)]
    finally:
        for stub in (receiver, proxy):
            stub.close()
            stub.srv.server_close()
