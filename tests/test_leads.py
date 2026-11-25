"""Життєвий цикл заявки: ідемпотентність (рівень БД), сталий outbox, повтори, ін'єкція збоїв доставки, перезапуск.
Кожен тест піднімає власний server/app.py (окрема БД) і, де треба, локальний стаб Telegram/вебхука."""
import json, os, signal, socket, sqlite3, subprocess, sys, tempfile, threading, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
LEAD = {'type': 'rent', 'subject': 'Екскаватор JCB JS220LC', 'method': 'phone', 'contact': '067 123 45 67', 'hours': '16'}


def _port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p


class Srv:
    def __init__(self, db, **env):
        self.port = _port(); self.base = f'http://127.0.0.1:{self.port}'; self.db = db
        self.data = Path(env.pop('PBT_DATA_DIR', None) or tempfile.mkdtemp(prefix='pbt-srv-data-'))   # журнал і сіль — свої, не репозиторні; незалежно від каталогу БД
        e = {**os.environ, 'PORT': str(self.port), 'HOST': '127.0.0.1', 'LEAD_DB': str(db), 'PBT_DATA_DIR': str(self.data), 'RATE_ANY_10MIN': '10000',
             'RATE_LEAD_10MIN': '10000', 'RATE_LEAD_DAY': '10000', 'TELEGRAM_BOT_TOKEN': '', 'TELEGRAM_CHAT_ID': '',
             'LEAD_WEBHOOK_URL': '', 'LEAD_WEBHOOK_SECRET': '', 'DELIVERY_POLL_S': '0.1', 'DELIVERY_BACKOFF_S': '0.05',
             'DELIVERY_TIMEOUT': '1', **{k: str(v) for k, v in env.items()}}
        self.p = subprocess.Popen([sys.executable, str(ROOT / 'server' / 'app.py')], env=e, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(self.base + '/api/health', timeout=.5); return
            except urllib.error.HTTPError:          # сервер відповів (напр. 503 здоров'я) — піднявся
                return
            except Exception:  # noqa: BLE001
                time.sleep(.05)
        self.p.kill(); self.p.wait(5)                # не лишати сироту: фікстура ще не знає про цей процес
        raise RuntimeError('server did not start')

    def post(self, data, key=None):
        h = {'Content-Type': 'application/json', 'Origin': self.base}
        if key is not None:
            h['Idempotency-Key'] = key
        req = urllib.request.Request(self.base + '/api/lead', json.dumps(data).encode(), h, method='POST')
        t = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read()), time.perf_counter() - t
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b'{}'), time.perf_counter() - t

    def kill(self, hard=True):
        self.p.send_signal(signal.SIGKILL if hard else signal.SIGTERM); self.p.wait(5)

    def rows(self, sql, *a):
        c = sqlite3.connect(self.db); r = c.execute(sql, a).fetchall(); c.close(); return r


class Stub:
    """Локальний приймач: script — послідовність відповідей (код або 'hang'); далі — 200."""
    def __init__(self, script=()):
        self.script, self.hits, stub = list(script), [], self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get('Content-Length') or 0))
                stub.hits.append((self.path, body, dict(self.headers)))
                act = stub.script.pop(0) if stub.script else 200
                if act == 'hang':
                    time.sleep(3); return
                if act == 'reset':                 # обрив: RST без відповіді
                    import struct
                    self.request.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0)); self.request.close()
                    self.close_connection = True; return
                self.send_response(act); self.send_header('Content-Length', '2'); self.end_headers(); self.wfile.write(b'{}')

            def log_message(self, *a):
                pass
        self.srv = ThreadingHTTPServer(('127.0.0.1', 0), H); self.url = f'http://127.0.0.1:{self.srv.server_address[1]}'
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()


def wait_for(fn, timeout=8):
    t = time.time()
    while time.time() - t < timeout:
        v = fn()
        if v:
            return v
        time.sleep(.05)
    return fn()


@pytest.fixture
def srv(tmp_path):
    made = []

    def make(**env):
        s = Srv(tmp_path / 'leads.db', **env); made.append(s); return s
    yield make
    for s in made:
        if s.p.poll() is None:
            s.kill()


# ─── ідемпотентність ─────────────────────────────────────
def test_same_key_same_payload_is_one_lead(srv):
    s = srv()
    a, b = s.post(LEAD, 'k-000000000001'), s.post(LEAD, 'k-000000000001')
    assert a[0] == b[0] == 201 and a[1]['ref'] == b[1]['ref'] and b[1].get('replayed') is True
    assert s.rows('SELECT count(*) FROM leads') == [(1,)]


def test_same_key_different_payload_is_conflict(srv):
    s = srv()
    assert s.post(LEAD, 'k-000000000002')[0] == 201
    code, j, _ = s.post({**LEAD, 'hours': '17'}, 'k-000000000002')
    assert code == 409 and j['error'] == 'idempotency_conflict'
    assert s.rows('SELECT count(*) FROM leads') == [(1,)]


def test_different_keys_same_payload_are_separate_leads(srv):
    s = srv()
    assert s.post(LEAD, 'k-000000000003')[1]['ref'] != s.post(LEAD, 'k-000000000004')[1]['ref']
    assert s.rows('SELECT count(*) FROM leads') == [(2,)]


def test_no_key_keeps_previous_behaviour(srv):
    s = srv()
    s.post(LEAD); s.post(LEAD)
    assert s.rows('SELECT count(*) FROM leads') == [(2,)]


@pytest.mark.parametrize('key', ['short', 'x' * 101, 'bad key!', 'a/b/c/d/e/f'])
def test_malformed_key_rejected(srv, key):
    s = srv()
    code, j, _ = s.post(LEAD, key)
    assert code == 400 and j['error'] == 'idempotency_key'
    assert s.rows('SELECT count(*) FROM leads') == [(0,)]


def test_concurrent_duplicates_are_one_lead(srv):
    s = srv()
    with ThreadPoolExecutor(16) as ex:
        res = list(ex.map(lambda _: s.post(LEAD, 'k-concurrent-01'), range(16)))
    assert {r[0] for r in res} == {201} and len({r[1]['ref'] for r in res}) == 1
    assert s.rows('SELECT count(*) FROM leads') == [(1,)]


def test_concurrent_duplicates_replay_at_strict_quota(srv):
    # An in-flight identical key must remain a 201 replay, not become a 429
    # after another request atomically reserves the only available lead slot.
    s = srv(RATE_LEAD_10MIN='1', RATE_LEAD_DAY='1')
    with ThreadPoolExecutor(16) as ex:
        responses = list(ex.map(lambda _: s.post(LEAD, 'k-concurrent-quota-01'), range(16)))
    assert all(response[0] == 201 for response in responses), responses
    assert len({response[1]['ref'] for response in responses}) == 1
    assert s.rows('SELECT count(*) FROM leads') == [(1,)]


def test_key_survives_restart(srv):
    s = srv(); ref = s.post(LEAD, 'k-restart-0001')[1]['ref']; s.kill()
    s2 = srv()
    assert s2.post(LEAD, 'k-restart-0001')[1]['ref'] == ref and s2.rows('SELECT count(*) FROM leads') == [(1,)]


def test_uniqueness_is_enforced_by_the_database(srv):
    s = srv(); s.post(LEAD, 'k-db-unique-01'); s.kill()
    c = sqlite3.connect(s.db)
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO leads(created,type,payload,idem_key) VALUES('t','rent','{}','k-db-unique-01')")
    c.close()


def test_migration_keeps_legacy_database(tmp_path, srv):
    """Стара схема (без idem_key/payload_hash/outbox) з наявною заявкою: сервер мігрує адитивно, стара заявка ціла."""
    db = tmp_path / 'leads.db'; c = sqlite3.connect(db)
    c.execute('CREATE TABLE leads(id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT NOT NULL, type TEXT NOT NULL, payload TEXT NOT NULL, ip_hash TEXT, ua TEXT, delivered TEXT)')
    c.execute("INSERT INTO leads(created,type,payload,delivered) VALUES('2026-09-01','rent','{\"subject\":\"old\"}','telegram')"); c.commit(); c.close()
    s = srv()
    assert s.post(LEAD, 'k-legacy-00001')[1]['ref'] == 'PBT-000002'
    assert s.rows('SELECT id, payload, delivered, idem_key FROM leads ORDER BY id')[0] == (1, '{"subject":"old"}', 'telegram', None)


# ─── outbox і доставка ───────────────────────────────────
def test_response_does_not_wait_for_hanging_webhook(srv):
    st = Stub(['hang'])
    s = srv(LEAD_WEBHOOK_URL=st.url + '/hook', LEAD_WEBHOOK_SECRET='sec', DELIVERY_TIMEOUT='2')
    code, j, dt = s.post(LEAD, 'k-hang-000001')
    st.close()
    assert code == 201 and dt < 1.0, dt           # раніше: відповідь після 8 + 8 с таймаутів доставки
    assert s.rows('SELECT count(*) FROM outbox') == [(1,)]


def test_successful_webhook_with_never_finished_body_does_not_retry_or_block(srv):
    """A 2xx acknowledgement is complete at headers; a trickled body must not cause duplicates."""
    import hashlib
    import hmac
    seen = []

    class SlowBody(BaseHTTPRequestHandler):
        def do_POST(self):
            raw = self.rfile.read(int(self.headers['Content-Length']))
            seen.append((raw, {k.lower(): v for k, v in self.headers.items()}))
            self.send_response(200)
            self.send_header('Content-Length', '65536')
            self.end_headers()
            self.wfile.write(b'!')  # Old urlopen(...).read() waited for the missing 65535 bytes.
            self.wfile.flush()
            time.sleep(4)

        def log_message(self, *args):
            pass

    receiver = ThreadingHTTPServer(('127.0.0.1', 0), SlowBody)
    receiver.daemon_threads = True
    worker = threading.Thread(target=receiver.serve_forever, daemon=True)
    worker.start()
    try:
        url = f'http://127.0.0.1:{receiver.server_address[1]}/hook'
        s = srv(LEAD_WEBHOOK_URL=url, LEAD_WEBHOOK_SECRET='secret',
                DELIVERY_TIMEOUT='1', DELIVERY_BACKOFF_S='10')
        status, result, _ = s.post(LEAD, 'k-trickle-ack-00001')
        assert status == 201 and result['ok']
        assert wait_for(lambda: s.rows("SELECT status, attempts FROM outbox") == [('delivered', 1)] or None,
                        timeout=2.5), 'success body was consumed or retried'
        assert len(seen) == 1
        raw, headers = seen[0]
        assert json.loads(raw)['id'] == 1
        assert hmac.compare_digest(headers['x-pbt-signature'],
                                   hmac.new(b'secret', raw, hashlib.sha256).hexdigest())
        assert s.rows('SELECT count(*) FROM leads') == [(1,)]
    finally:
        receiver.shutdown()
        receiver.server_close()
        worker.join(timeout=3)


def test_transient_failures_retry_until_delivered(srv):
    st = Stub([500, 429])
    s = srv(LEAD_WEBHOOK_URL=st.url + '/hook', LEAD_WEBHOOK_SECRET='sec')
    s.post(LEAD, 'k-retry-000001')
    row = wait_for(lambda: [r for r in s.rows('SELECT status, attempts, last_error FROM outbox') if r[0] == 'delivered'])
    st.close()
    assert row == [('delivered', 3, None)] and len(st.hits) == 3
    assert s.rows('SELECT delivered FROM leads') == [('webhook',)]
    body = json.loads(st.hits[-1][1])
    import hashlib, hmac
    assert {k.lower(): v for k, v in st.hits[-1][2].items()}['x-pbt-signature'] == hmac.new(b'sec', st.hits[-1][1], hashlib.sha256).hexdigest() and body['id'] == 1


def test_permanent_client_error_is_not_retried(srv):
    st = Stub([400])
    s = srv(LEAD_WEBHOOK_URL=st.url + '/hook', LEAD_WEBHOOK_SECRET='sec')
    s.post(LEAD, 'k-perm-000001')
    row = wait_for(lambda: [r for r in s.rows('SELECT status, attempts, last_error FROM outbox') if r[0] == 'failed'])
    time.sleep(.5)
    st.close()
    assert row == [('failed', 1, 'HTTP 400')] and len(st.hits) == 1
    assert s.rows('SELECT count(*) FROM leads') == [(1,)]          # збій доставки не видаляє заявку


def test_connection_refused_is_bounded(srv):
    dead = f'http://127.0.0.1:{_port()}/hook'
    s = srv(LEAD_WEBHOOK_URL=dead, LEAD_WEBHOOK_SECRET='sec', DELIVERY_MAX_ATTEMPTS='3')
    s.post(LEAD, 'k-refused-0001')
    row = wait_for(lambda: [r for r in s.rows('SELECT status, attempts FROM outbox') if r[0] == 'failed'])
    assert row == [('failed', 3)]
    assert s.rows('SELECT count(*) FROM leads') == [(1,)]


def test_crash_after_commit_before_delivery_is_recovered(srv):
    """Процес гине після коміту, до доставки (воркер вимкнено) → після перезапуску незавершена доставка виконується."""
    st = Stub()
    s = srv(LEAD_WEBHOOK_URL=st.url + '/hook', LEAD_WEBHOOK_SECRET='sec', DELIVERY_WORKER='0')
    assert s.post(LEAD, 'k-crash-000001')[0] == 201
    s.kill(hard=True)
    assert s.rows('SELECT status FROM outbox') == [('pending',)] and st.hits == []
    s2 = srv(LEAD_WEBHOOK_URL=st.url + '/hook', LEAD_WEBHOOK_SECRET='sec')
    row = wait_for(lambda: [r for r in s2.rows('SELECT status FROM outbox') if r[0] == 'delivered'])
    st.close()
    assert row == [('delivered',)] and len(st.hits) == 1


def test_per_channel_state_no_resend_of_delivered_channel(srv):
    """Telegram доставлено з першої спроби, вебхук падає двічі: Telegram більше не надсилається."""
    tg, wh = Stub(), Stub([500, 500])
    s = srv(TELEGRAM_BOT_TOKEN='123:abc', TELEGRAM_CHAT_ID='42', TELEGRAM_API_BASE=tg.url,
            LEAD_WEBHOOK_URL=wh.url + '/hook', LEAD_WEBHOOK_SECRET='sec')
    s.post(LEAD, 'k-channels-001')
    rows = wait_for(lambda: (lambda r: r if all(x[1] == 'delivered' for x in r) and len(r) == 2 else None)(
        s.rows('SELECT channel, status, attempts FROM outbox ORDER BY channel')))
    tg.close(); wh.close()
    assert rows == [('telegram', 'delivered', 1), ('webhook', 'delivered', 3)]
    assert len(tg.hits) == 1 and len(wh.hits) == 3 and tg.hits[0][0] == '/bot123:abc/sendMessage'
    assert s.rows('SELECT delivered FROM leads') == [('telegram,webhook',)]


def test_webhook_without_secret_creates_no_outbox_job(srv):
    s = srv(LEAD_WEBHOOK_URL='http://127.0.0.1:9/hook')
    assert s.post(LEAD, 'k-nosecret-001')[0] == 201
    assert s.rows('SELECT count(*) FROM outbox') == [(0,)]


def test_replay_is_not_blocked_by_and_does_not_consume_lead_quota(srv):
    """Квота 1 заявка / 10 хв: повтор прийнятої заявки → та сама заявка (не 429); нова заявка — 429."""
    s = srv(RATE_LEAD_10MIN='1')
    a = s.post(LEAD, 'k-quota-000001')
    b = s.post(LEAD, 'k-quota-000001')
    c = s.post({**LEAD, 'hours': '24'}, 'k-quota-000002')
    assert a[0] == 201 and b[0] == 201 and b[1]['ref'] == a[1]['ref'] and c[0] == 429
    assert s.rows('SELECT count(*) FROM leads') == [(1,)]


def test_S14_proxy_headers_untrusted_by_default(srv):
    """Без явного TRUST_PROXY=1: X-Forwarded-For не змінює ідентичність для лімітів, X-Forwarded-Proto не вмикає HSTS."""
    s = srv(RATE_LEAD_10MIN='3', TRUST_PROXY='')

    def lead(ip, key):
        h = {'Content-Type': 'application/json', 'Origin': s.base, 'X-Forwarded-For': ip, 'Idempotency-Key': key}
        req = urllib.request.Request(s.base + '/api/lead', json.dumps(LEAD).encode(), h, method='POST')
        try:
            with urllib.request.urlopen(req) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
    assert [lead('203.0.113.7', f'k-proxy-00000{i}') for i in range(3)] == [201] * 3
    assert lead('198.51.100.9', 'k-proxy-000009') == 429          # підроблений XFF не дає «нового клієнта»
    r = urllib.request.urlopen(urllib.request.Request(s.base + '/', headers={'X-Forwarded-Proto': 'https'}))
    assert 'Strict-Transport-Security' not in r.headers


def test_S14_proxy_trust_is_explicit_opt_in(srv):
    s = srv(RATE_LEAD_10MIN='1', TRUST_PROXY='1')
    codes = []
    for ip, k in (('203.0.113.7', 'k-optin-000001'), ('203.0.113.7', 'k-optin-000002'), ('198.51.100.9', 'k-optin-000003')):
        h = {'Content-Type': 'application/json', 'Origin': s.base, 'X-Forwarded-For': ip, 'Idempotency-Key': k}
        try:
            with urllib.request.urlopen(urllib.request.Request(s.base + '/api/lead', json.dumps(LEAD).encode(), h, method='POST')) as r:
                codes.append(r.status)
        except urllib.error.HTTPError as e:
            codes.append(e.code)
    assert codes == [201, 429, 201]
    r = urllib.request.urlopen(urllib.request.Request(s.base + '/', headers={'X-Forwarded-Proto': 'https'}))
    assert r.headers['Strict-Transport-Security'] == 'max-age=15552000'


def test_S14_deployment_unit_opts_in():
    assert 'Environment=TRUST_PROXY=1' in (ROOT / 'ops' / 'systemd' / 'pbt-site.service').read_text(encoding='utf-8')


def test_power_guard_marker_suppresses_the_health_watchdog():
    unit = (ROOT / 'ops' / 'systemd' / 'pbt-site-health.service').read_text(encoding='utf-8')
    assert 'ConditionPathExists=!%h/.local/state/pbt-power-guard/stopped.json' in unit


def test_timeout_reset_and_408_are_transient(srv):
    """Таймаут, обрив з'єднання (RST) і 408 — тимчасові: повтор до успіху, лічильник спроб і стан — у БД."""
    st = Stub(['hang', 'reset', 408])
    s = srv(LEAD_WEBHOOK_URL=st.url + '/hook', LEAD_WEBHOOK_SECRET='sec', DELIVERY_TIMEOUT='1')
    s.post(LEAD, 'k-transient-01')
    row = wait_for(lambda: [r for r in s.rows('SELECT status, attempts, last_error, delivered_at FROM outbox') if r[0] == 'delivered'], timeout=15)
    st.close()
    assert row and row[0][:3] == ('delivered', 4, None) and row[0][3]
    assert len(st.hits) == 4


def test_lead_and_outbox_commit_atomically(srv, tmp_path):
    """Заявка й завдання доставки — одна транзакція: збій вставки в outbox → жодної заявки (без часткового прийому), відповідь 500."""
    s = srv(); s.kill()                                   # створює схему
    c = sqlite3.connect(s.db)
    c.execute("CREATE TRIGGER outbox_fail BEFORE INSERT ON outbox BEGIN SELECT RAISE(ABORT, 'injected'); END"); c.commit(); c.close()
    s2 = srv(LEAD_WEBHOOK_URL='http://127.0.0.1:9/hook', LEAD_WEBHOOK_SECRET='sec')
    code, j, _ = s2.post(LEAD, 'k-atomic-00001')
    assert code == 500 and j['error'] == 'storage'
    assert s2.rows('SELECT count(*) FROM leads') == [(0,)] and s2.rows('SELECT count(*) FROM outbox') == [(0,)]

# ─── malformed JSON Unicode scalar boundary ──────────────────────
@pytest.mark.parametrize('field', ('subject', 'place', 'name', 'comment'))
def test_escaped_lone_surrogate_is_422_and_not_persisted(srv, field):
    """An ASCII-escaped isolated UTF-16 surrogate must not drop the HTTP reply."""
    s = srv(DELIVERY_WORKER='0')
    data = {**LEAD, field: 'valid' + chr(0xD800) + 'text'}
    raw = json.dumps(data, ensure_ascii=True).encode('ascii')
    req = urllib.request.Request(
        s.base + '/api/lead', raw,
        {'Origin': s.base, 'Content-Type': 'application/json',
         'Idempotency-Key': 'k-surrogate-negative-001'}, method='POST')
    with pytest.raises(urllib.error.HTTPError) as rejected:
        urllib.request.urlopen(req, timeout=4)
    assert rejected.value.code == 422
    response = json.loads(rejected.value.read())
    assert response['error'] == 'validation' and field in response['fields']
    assert s.rows('SELECT count(*) FROM leads') == [(0,)]
    assert s.rows('SELECT count(*) FROM outbox') == [(0,)]


def test_valid_json_surrogate_pair_preserves_201_and_emoji(srv):
    """json.loads recombines a paired surrogate into a valid Unicode scalar."""
    s = srv(DELIVERY_WORKER='0')
    data = {**LEAD, 'subject': 'Екскаватор ' + chr(0x1F9E0)}
    raw = json.dumps(data, ensure_ascii=True).encode('ascii')
    req = urllib.request.Request(
        s.base + '/api/lead', raw,
        {'Origin': s.base, 'Content-Type': 'application/json',
         'Idempotency-Key': 'k-surrogate-valid-pair-01'}, method='POST')
    with urllib.request.urlopen(req, timeout=4) as accepted:
        assert accepted.status == 201
        assert json.loads(accepted.read())['ref'] == 'PBT-000001'
    assert s.rows('SELECT count(*) FROM leads') == [(1,)]
    assert json.loads(s.rows('SELECT payload FROM leads')[0][0])['subject'] == data['subject']


# ─── privacy: neither full peer IP nor URL query/Origin in durable logs ───
def test_http_access_and_rejected_origin_logs_are_pseudonymous(srv):
    """Negative falsifier: the old handler emitted raw XFF, query and Origin."""
    s = srv(TRUST_PROXY='1', DELIVERY_WORKER='0')
    journal = s.data / 'server.log'
    offset = journal.stat().st_size
    raw_ip = '198.51.100.237'
    marker = 'pbt-private-query-314159'
    request = urllib.request.Request(
        s.base + '/api/health?contact=' + marker,
        headers={'X-Forwarded-For': raw_ip})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status in (200, 503)
    except urllib.error.HTTPError as exc:
        assert exc.code == 503
    invalid_origin = 'https://untrusted.invalid/private/' + marker
    rejected = urllib.request.Request(
        s.base + '/api/lead', json.dumps(LEAD).encode('utf-8'),
        {'Content-Type': 'application/json', 'Origin': invalid_origin,
         'X-Forwarded-For': raw_ip}, method='POST')
    with pytest.raises(urllib.error.HTTPError) as response:
        urllib.request.urlopen(rejected, timeout=5)
    assert response.value.code == 403
    journal_delta = journal.read_bytes()[offset:].decode('utf-8')
    assert raw_ip not in journal_delta
    assert '127.0.0.1 ' not in journal_delta
    assert marker not in journal_delta
    assert invalid_origin not in journal_delta
    assert 'client_hash=' in journal_delta
    assert 'status=403' in journal_delta
