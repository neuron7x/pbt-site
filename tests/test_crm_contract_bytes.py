"""Наказ А1, крок 0: контракт заявки з CRM — зафіксовані байти, до розкладання server/app.py.

AGENTS.md §1: сайт шле тіло заявки POST-запитом на /api/v1/site/leads CRM; підпис — HMAC-SHA256 тіла в X-PBT-Signature;
повтор — з тим самим id. Зміна поля = зміна CRM. Ця рука тримає саме байти на дроті: кожне переміщення коду сервера
судиться нею. Секрет тут — тестовий рядок, не справжній.
"""
import hashlib
import hmac
import json
from pathlib import Path

from test_leads import Stub, srv, wait_for  # noqa: F401

VECTOR = json.loads((Path(__file__).resolve().parent / 'contracts' / 'crm_lead_vector.json').read_text(encoding='utf-8'))
# золотий вектор: той самий файл судить контракт і в репозиторії CRM — розбіжність червона з обох боків.
# рівно ці байти отримує CRM: порядок ключів, пробіли після «,» і «:», кирилиця без \u-екранування, km: null, телефон у E.164
SECRET, PATH, FULL = VECTOR['secret'], VECTOR['path'], VECTOR['form']
WIRE, SIGNATURE = VECTOR['body'].encode('utf-8'), VECTOR['signature']
KEYS = ('id', 'type', 'subject', 'hours', 'km', 'place', 'date', 'name', 'method', 'contact', 'comment')


def _deliver(srv, lead, script=(), hits=1):
    stub = Stub(script)
    server = srv(LEAD_WEBHOOK_URL=stub.url + PATH, LEAD_WEBHOOK_SECRET=SECRET)
    answer = server.post(lead, 'k-contract-0001')
    wait_for(lambda: len(stub.hits) >= hits and server.rows("SELECT 1 FROM outbox WHERE status != 'pending'"))
    stub.close()
    return server, answer, [(path, body, {k.lower(): v for k, v in headers.items()}) for path, body, headers in stub.hits]


def test_the_golden_vector_is_self_consistent_and_pinned():
    assert hmac.new(SECRET.encode(), WIRE, hashlib.sha256).hexdigest() == SIGNATURE
    assert (len(WIRE), hashlib.sha256(WIRE).hexdigest()) == (VECTOR['body_bytes'], VECTOR['body_sha256'])
    assert json.loads(WIRE)['id'] == VECTOR['lead_id'] and (VECTOR['signature_header'], VECTOR['method']) == ('X-PBT-Signature', 'POST')
    # закріплено тут, а не лише у файлі: правка вектора без правки тесту — червона (зміна контракту = зміна CRM)
    assert (len(WIRE), SIGNATURE) == (317, 'ffad891e5290945a8ec4ab29ba39131b9daff09eda55c02b5266276e77808fc9')


def test_a_fixed_lead_reaches_the_crm_as_exactly_these_bytes(srv):
    server, answer, hits = _deliver(srv, FULL)
    assert answer[:2] == (201, {'ok': True, 'ref': 'PBT-000001'})
    assert len(hits) == 1
    path, body, headers = hits[0]
    assert path == PATH
    assert body == WIRE
    assert headers['x-pbt-signature'] == SIGNATURE
    assert headers['content-type'] == 'application/json' and headers['content-length'] == str(len(WIRE))
    assert server.rows('SELECT status, attempts FROM outbox') == [('delivered', 1)]


def test_a_retry_repeats_the_same_id_body_and_signature(srv):
    server, _, hits = _deliver(srv, FULL, script=[500, 429], hits=3)
    assert [(path, body, headers['x-pbt-signature']) for path, body, headers in hits] == [(PATH, WIRE, SIGNATURE)] * 3
    assert server.rows('SELECT status, attempts FROM outbox') == [('delivered', 3)]
    assert server.rows('SELECT count(*) FROM leads') == [(1,)]


def test_a_minimal_lead_keeps_the_same_fields_and_order(srv):
    _, answer, hits = _deliver(srv, {'type': 'material', 'subject': 'Пісок', 'method': 'telegram', 'contact': '@olena_pb'})
    assert answer[0] == 201 and len(hits) == 1
    _, body, headers = hits[0]
    sent = json.loads(body)
    assert tuple(sent) == KEYS                                              # поля ті самі й у тому самому порядку
    assert sent['id'] == 1 and sent['type'] == 'material' and sent['method'] == 'telegram' and sent['contact'] == '@olena_pb'
    assert headers['x-pbt-signature'] == hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    assert body == json.dumps(sent, ensure_ascii=False).encode('utf-8')     # формат серіалізації той самий, що у WIRE
