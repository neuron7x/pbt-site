"""Telegram delivery must preserve full accepted Unicode input without URL-encoding expansion."""
import json
import urllib.request

from test_leads import LEAD, Stub, srv, wait_for  # noqa: F401


def test_valid_maximum_emoji_fields_reach_telegram_once(srv):
    # A 16384-byte form-urlencoded child cap used to reject this valid lead.
    # Send UTF-8 JSON as a browser would, not Python json.dumps ASCII escapes.
    emoji = '🧠'
    valid = {**LEAD, 'subject': emoji * 160, 'place': emoji * 160,
             'name': emoji * 60, 'comment': emoji * 1000}
    receiver = Stub()
    try:
        server = srv(TELEGRAM_BOT_TOKEN='123:abc', TELEGRAM_CHAT_ID='42',
                     TELEGRAM_API_BASE=receiver.url, DELIVERY_MAX_ATTEMPTS='2',
                     DELIVERY_TIMEOUT='2')
        # Independently reproduce the original 16-KiB failure from the same
        # accepted Unicode fields before testing the fixed real transport.
        from urllib.parse import urlencode
        old_text = "Заявка LA-000001\n" + "\n".join(
            f"{key}: {value}" for key, value in valid.items() if value not in (None, ""))
        legacy = urlencode({'chat_id': '42', 'text': old_text[:4000]}).encode()
        assert len(legacy) > 16384
        raw = json.dumps(valid, ensure_ascii=False).encode('utf-8')
        assert len(raw) < 8192
        request = urllib.request.Request(
            server.base + '/api/lead', raw,
            {'Origin': server.base, 'Content-Type': 'application/json',
             'Idempotency-Key': 'k-telegram-emoji-0001'}, method='POST')
        with urllib.request.urlopen(request, timeout=8) as result:
            assert result.status == 201
            assert json.loads(result.read())['ok'] is True
        assert wait_for(
            lambda: server.rows(
                "SELECT status, attempts FROM outbox WHERE channel='telegram'"
            ) == [('delivered', 1)] or None, timeout=8
        ), server.rows("SELECT status, attempts, last_error FROM outbox")
        assert server.rows("SELECT count(*) FROM leads") == [(1,)]
        assert len(receiver.hits) == 1
        path, body, headers = receiver.hits[0]
        assert path == '/bot123:abc/sendMessage'
        assert headers['Content-Type'] == 'application/json'
        assert len(body) < 16384  # Original child cap remains enforced.
        message = json.loads(body)
        assert message['chat_id'] == '42'
        assert emoji * 160 in message['text']
        assert emoji * 1000 in message['text']
        assert len(message['text']) <= 4000
        assert '%F0%9F' not in body.decode('utf-8')
    finally:
        receiver.close()
