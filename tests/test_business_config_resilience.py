"""Unavailable business identity must not stop the API or durable lead delivery."""
import json
from pathlib import Path
import shutil
import urllib.request

import pytest

import test_leads
from test_leads import LEAD, Stub, srv, wait_for  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    tree = tmp_path / 'site'
    shutil.copytree(ROOT / 'server', tree / 'server', ignore=shutil.ignore_patterns('__pycache__'))
    (tree / 'web').mkdir()
    (tree / 'config').mkdir()
    monkeypatch.setattr(test_leads, 'ROOT', tree)
    return tree / 'config/business.json'


@pytest.mark.parametrize('document, public', [
    pytest.param(None, {}, id='null-root'),
    pytest.param([], {}, id='array-root'),
    pytest.param('unavailable', {}, id='string-root'),
    pytest.param({'brand': None, 'contacts': None, '_status': 'internal'},
                 {'brand': None, 'contacts': None}, id='nullable-partial'),
    pytest.param({'brand': 'unavailable'}, {'brand': 'unavailable'}, id='scalar-brand'),
    pytest.param({'brand': {'name': None}}, {'brand': {'name': None}}, id='null-name'),
    pytest.param({'brand': {'name': ['unavailable']}},
                 {'brand': {'name': ['unavailable']}}, id='nontext-name'),
    pytest.param({'brand': {'name': '  '}}, {'brand': {'name': '  '}}, id='blank-name'),
])
def test_unavailable_identity_keeps_api_and_telegram_working(isolated_config, srv, document, public):
    isolated_config.write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
    receiver = Stub()
    try:
        server = srv(TELEGRAM_BOT_TOKEN='123:abc', TELEGRAM_CHAT_ID='42', TELEGRAM_API_BASE=receiver.url)
        with urllib.request.urlopen(server.base + '/api/config', timeout=3) as response:
            assert response.status == 200
            assert json.load(response) == public
        status, accepted, _ = server.post(LEAD, 'k-business-config-0001')
        assert status == 201 and accepted['ref'] == 'PBT-000001'
        assert wait_for(lambda: server.rows('SELECT status, attempts FROM outbox') == [('delivered', 1)])
        assert len(receiver.hits) == 1
        message = json.loads(receiver.hits[0][1])
        assert message['text'].splitlines()[0] == 'Сайт · заявка №000001'
    finally:
        receiver.close()
        receiver.srv.server_close()


def test_valid_business_config_is_published_unchanged_without_private_status(isolated_config, srv):
    canonical = json.loads((ROOT / 'config/business.json').read_text(encoding='utf-8'))
    isolated_config.write_text(json.dumps(canonical, ensure_ascii=False), encoding='utf-8')
    server = srv()
    with urllib.request.urlopen(server.base + '/api/config', timeout=3) as response:
        assert response.status == 200
        assert json.load(response) == {key: value for key, value in canonical.items() if key != '_status'}
