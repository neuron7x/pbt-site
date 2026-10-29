"""Дискримінаційні тести меж сервера й збірки: кожен закриває мутанта, що виживав на попередньому наборі
(незалежний аудит J, 213ccb0: M01–M23). Ідентифікатор мутанта — у назві/докстрінгу тесту."""
import base64, hashlib, hmac, json, re, socket, sqlite3, time, threading, urllib.error, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import pytest
from test_leads import LEAD, Srv, Stub, _port, srv, wait_for  # noqa: F401  (фікстура srv)

ROOT = Path(__file__).resolve().parent.parent


def _headers(base, path='/', extra=None):
    req = urllib.request.Request(base + path, headers=extra or {})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.headers


def _lead(s, key, xff=None, origin=None, data=None):
    h = {'Content-Type': 'application/json', 'Origin': origin or s.base, 'Idempotency-Key': key}
    if xff is not None:
        h['X-Forwarded-For'] = xff
    req = urllib.request.Request(s.base + '/api/lead', json.dumps(data or LEAD).encode(), h, method='POST')
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


# ─── заголовки / CSP (M01–M04, M16) ─────────────────────────
def test_csp_is_exact_and_hashes_match_real_inline_scripts(srv):
    """M01 default-src *, M02 фіктивний хеш, M03 unsafe-eval: CSP розбирається по директивах, script-src = 'self' + хеші
    САМЕ тих inline-скриптів, що є в web/*.html (кожен хеш має відповідник і навпаки)."""
    s = srv()
    _, h = _headers(s.base)
    csp = dict((d.split()[0], d.split()[1:]) for d in (x.strip() for x in h['Content-Security-Policy'].split(';')) if d)
    assert csp['default-src'] == ["'self'"] and csp['frame-ancestors'] == ["'none'"] and csp['base-uri'] == ["'self'"]
    assert csp['connect-src'] == ["'self'"] and csp['form-action'] == ["'self'"] and csp['img-src'] == ["'self'", 'data:']
    src = csp['script-src']
    assert src[0] == "'self'" and all(t.startswith("'sha256-") for t in src[1:]), src
    want = set()
    for f in (ROOT / 'web').glob('*.html'):
        for m in re.finditer(r'<script>(.*?)</script>', f.read_text(encoding='utf-8'), re.S):
            want.add("'sha256-" + base64.b64encode(hashlib.sha256(m.group(1).encode()).digest()).decode() + "'")
    assert set(src[1:]) == want and want


def test_security_header_values_exact(srv):
    """M04: Referrer-Policy/Permissions-Policy/nosniff/DENY — точні значення на HTML, статиці й API; M16: API — no-store."""
    s = srv()
    for path in ('/', '/css/site.css', '/media/seal.webp', '/api/health', '/api/config'):
        _, h = _headers(s.base, path)
        assert h['Referrer-Policy'] == 'strict-origin-when-cross-origin', path
        assert h['Permissions-Policy'] == 'camera=(), microphone=(), geolocation=()', path
        assert h['X-Content-Type-Options'] == 'nosniff' and h['X-Frame-Options'] == 'DENY', path
    for path in ('/api/health', '/api/config'):
        assert _headers(s.base, path)[1]['Cache-Control'] == 'no-store', path
    code, j = _lead(s, 'k-hdr-0000001')
    assert code == 201


# ─── ідентичність клієнта за проксі (M05, M06) ──────────────
def test_xff_uses_rightmost_entry(srv):
    """M05: береться КРАЙНІЙ ПРАВИЙ запис (доданий довіреним проксі), не лівий (контрольований клієнтом)."""
    s = srv(TRUST_PROXY='1', RATE_LEAD_10MIN='1')
    assert _lead(s, 'k-xff-0000001', xff='1.1.1.1, 203.0.113.7')[0] == 201
    assert _lead(s, 'k-xff-0000002', xff='9.9.9.9, 203.0.113.7')[0] == 429     # той самий правий → той самий клієнт
    assert _lead(s, 'k-xff-0000003', xff='203.0.113.7, 198.51.100.9')[0] == 201


def test_xff_invalid_rightmost_falls_back_to_peer(srv):
    """M06: невалідний правий запис не стає ідентичністю (інакше довільний рядок = новий клієнт)."""
    s = srv(TRUST_PROXY='1', RATE_LEAD_10MIN='1')
    assert _lead(s, 'k-xffbad-00001', xff='not-an-ip-1')[0] == 201
    assert _lead(s, 'k-xffbad-00002', xff='not-an-ip-2')[0] == 429          # обидва → пір 127.0.0.1


# ─── квоти / Origin / honeypot (M07–M09) ─────────────────────
def test_daily_quota_enforced_independently(srv):
    """M07: денна квота діє навіть коли 10-хвилинна не вичерпана."""
    s = srv(RATE_LEAD_10MIN='100', RATE_LEAD_DAY='1')
    assert _lead(s, 'k-day-00000001')[0] == 201
    assert _lead(s, 'k-day-00000002', data={**LEAD, 'hours': '17'})[0] == 429


@pytest.mark.parametrize('origin', ['https://{h}.evil.tld', 'http://evil.tld/{h}', 'http://{h}:1', 'https://evil.tld?{h}', 'null'])
def test_origin_is_exact_match_not_substring(srv, origin):
    """M08: Origin порівнюється точно з http(s)://<Host>; підрядок хоста в чужому Origin — 403."""
    s = srv()
    o = origin.format(h=f'127.0.0.1:{s.port}')
    code, j = _lead(s, 'k-origin-00001', origin=o)
    assert code == 403 and j['error'] == 'origin', o
    assert s.rows('SELECT count(*) FROM leads') == [(0,)]


@pytest.mark.parametrize('hp', [[1], {'a': 1}, 'x' * 300, 'http://spam', 7])
def test_honeypot_any_non_empty_or_invalid_value_is_dropped(srv, hp):
    """M09: невалідний тип/довжина в пастці (None після safe()) — теж бот: тиха відповідь, нуль записів."""
    s = srv()
    code, j = _lead(s, 'k-hp-000000001', data={**LEAD, 'website': hp})
    assert (code, j.get('ref')) == (200, 'PBT-000000')
    assert s.rows('SELECT count(*) FROM leads') == [(0,)]


# ─── outbox: стеля затримки, пакет, класи помилок (M10, M11, M23) ─
def test_backoff_is_capped(srv):
    """M10: затримка повтору обмежена стелею 6 год навіть коли база × 2^(n−1) більша."""
    s = srv(LEAD_WEBHOOK_URL=f'http://127.0.0.1:{_port()}/hook', LEAD_WEBHOOK_SECRET='sec', DELIVERY_BACKOFF_S='30000')
    s.post(LEAD, 'k-cap-00000001')
    row = wait_for(lambda: s.rows('SELECT attempts, next_at - last_at FROM outbox WHERE attempts >= 1'))
    assert row and row[0][0] == 1 and 21599 <= row[0][1] <= 21601, row


def test_backlog_after_restart_drains_in_one_pass(srv):
    """M11: накопичені незавершені доставки після перезапуску обробляються одним проходом (пакет), а не по одній за опитування."""
    st = Stub()
    s = srv(LEAD_WEBHOOK_URL=st.url + '/hook', LEAD_WEBHOOK_SECRET='sec', DELIVERY_WORKER='0')
    for i in range(5):
        s.post({**LEAD, 'hours': f'{30 + i}'}, f'k-backlog-000{i}')
    s.kill()
    s2 = srv(LEAD_WEBHOOK_URL=st.url + '/hook', LEAD_WEBHOOK_SECRET='sec', DELIVERY_POLL_S='30')
    done = wait_for(lambda: s2.rows("SELECT count(*) FROM outbox WHERE status='delivered'")[0][0] == 5 or None, timeout=5)
    st.close()
    assert done and len(st.hits) == 5


def test_bounded_parallel_delivery_breaks_sequential_downstream_stall(srv):
    """Four queued webhook deliveries must enter the receiver concurrently.

    A single-threaded worker reaches the receiver barrier once, then times out.
    No wall-clock throughput estimate is inferred from this synchronization test.
    """
    gate = threading.Barrier(4)
    received = []
    errors = []
    lock = threading.Lock()

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers['Content-Length']))
            with lock:
                received.append((body, dict(self.headers)))
            try:
                gate.wait(timeout=6)
            except threading.BrokenBarrierError:
                with lock:
                    errors.append('receiver barrier timed out')
                self.send_response(503)
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            self.send_response(200)
            self.send_header('Content-Length', '2')
            self.end_headers()
            self.wfile.write(b'{}')

        def log_message(self, *args):
            pass

    receiver = ThreadingHTTPServer(('127.0.0.1', 0), Receiver)
    receiver.daemon_threads = True
    thread = threading.Thread(target=receiver.serve_forever, daemon=True)
    thread.start()
    try:
        url = f'http://127.0.0.1:{receiver.server_address[1]}/hook'
        s = srv(LEAD_WEBHOOK_URL=url, LEAD_WEBHOOK_SECRET='sec', DELIVERY_WORKER='0')
        for i in range(4):
            assert s.post(LEAD, f'k-parallel-{i:06d}')[0] == 201
        assert s.rows("SELECT count(*) FROM outbox WHERE status='pending'") == [(4,)]
        s.kill()
        restarted = srv(LEAD_WEBHOOK_URL=url, LEAD_WEBHOOK_SECRET='sec',
                        DELIVERY_CONCURRENCY='4', DELIVERY_POLL_S='30', DELIVERY_TIMEOUT='2')
        done = wait_for(lambda: restarted.rows("SELECT count(*) FROM outbox WHERE status='delivered'") == [(4,)],
                        timeout=9)
        assert done, 'webhook requests were serial or did not complete'
        assert not errors, errors
        assert len(received) == 4
        assert sorted(json.loads(body)['id'] for body, _ in received) == [1, 2, 3, 4]
        for body, headers in received:
            sig = {k.lower(): v for k, v in headers.items()}['x-pbt-signature']
            assert hmac.compare_digest(sig, hmac.new(b'sec', body, hashlib.sha256).hexdigest())
        assert restarted.rows("SELECT count(*) FROM outbox WHERE status='pending'") == [(0,)]
        assert restarted.rows("SELECT sum(attempts) FROM outbox") == [(4,)]
    finally:
        receiver.shutdown()
        receiver.server_close()
        thread.join(timeout=3)


def test_outbox_51_rows_after_restart_drains_before_next_poll(srv):
    """51 due rows must not incur an extra 30-second wait after the first 50."""
    st = Stub()
    try:
        s = srv(LEAD_WEBHOOK_URL=st.url + '/hook', LEAD_WEBHOOK_SECRET='sec', DELIVERY_WORKER='0')
        for i in range(51):
            assert s.post(LEAD, f'k-over50-{i:05d}')[0] == 201
        assert s.rows("SELECT count(*) FROM outbox WHERE status='pending'") == [(51,)]
        s.kill()
        restarted = srv(LEAD_WEBHOOK_URL=st.url + '/hook', LEAD_WEBHOOK_SECRET='sec', DELIVERY_POLL_S='30')
        done = wait_for(lambda: restarted.rows("SELECT count(*) FROM outbox WHERE status='delivered'") == [(51,)],
                        timeout=12)
        assert done, 'worker waited for the 30s poll interval with a due backlog'
        assert restarted.rows("SELECT count(*) FROM outbox WHERE status='pending'") == [(0,)]
        assert len(st.hits) == 51
        ids = [json.loads(body)['id'] for _, body, _ in st.hits]
        assert sorted(ids) == list(range(1, 52))
        for _, body, headers in st.hits:
            signature = {k.lower(): v for k, v in headers.items()}['x-pbt-signature']
            assert hmac.compare_digest(signature, hmac.new(b'sec', body, hashlib.sha256).hexdigest())
    finally:
        st.close()


def test_rate_identity_cardinality_is_bounded_without_quota_eviction(srv):
    """Many proxy identities cannot grow memory without bound or reset existing quotas."""
    s = srv(TRUST_PROXY='1', RATE_IP_CAP='2', RATE_ANY_10MIN='10',
            RATE_LEAD_10MIN='3', RATE_LEAD_DAY='3')
    for i in range(2):
        assert _lead(s, f'k-ipcap-{i:06d}', xff=f'203.0.113.{10 + i}')[0] == 201
    for i in range(64):
        code, data = _lead(s, f'k-flood-{i:06d}', xff=f'198.51.100.{i + 1}')
        assert (code, data.get('error')) == (429, 'rate')
    assert _lead(s, 'k-ipcap-000003', xff='203.0.113.10')[0] == 201
    assert s.rows('SELECT count(*) FROM leads') == [(3,)]
    assert s.rows('SELECT count(*) FROM outbox') == [(0,)]


def test_server_5xx_is_transient(srv):
    """M23: будь-яка 5xx (тут 501, 503) — тимчасова: повтор до успіху."""
    st = Stub([501, 503])
    s = srv(LEAD_WEBHOOK_URL=st.url + '/hook', LEAD_WEBHOOK_SECRET='sec')
    s.post(LEAD, 'k-5xx-00000001')
    row = wait_for(lambda: [r for r in s.rows('SELECT status, attempts FROM outbox') if r[0] == 'delivered'])
    st.close()
    assert row == [('delivered', 3)]


# ─── журнал / сіль / таймаут / здоров'я / HSTS (M12–M14, M21, M22) ─
def test_request_log_strips_control_characters(srv):
    """M12 (S9): керівні символи з рядка запиту не потрапляють у журнал (підробка записів/ESC-послідовності)."""
    s = srv()
    marker = f'LOGINJ{time.time_ns()}'
    with socket.create_connection(('127.0.0.1', s.port)) as c:
        c.sendall(f'GET /{marker}\x1b[31m\x07\x08 HTTP/1.0\r\n\r\n'.encode('latin-1')); c.recv(100)
    log = (ROOT / 'data' / 'server.log').read_bytes()
    line = [l for l in log.splitlines() if marker.encode() in l]
    assert line and all(b not in line[-1] for b in (b'\x1b', b'\x07', b'\x08')), line


def test_ip_hash_uses_secret_salt_not_constant(srv):
    """M13 (S10): без IP_HASH_SALT сіль — випадкова з data/.ip_salt, не константа."""
    s = srv(IP_HASH_SALT='')
    s.post(LEAD, 'k-salt-0000001')
    h = s.rows('SELECT ip_hash FROM leads')[0][0]
    salt = (ROOT / 'data' / '.ip_salt').read_text().strip()
    assert h == hmac.new(salt.encode(), b'127.0.0.1', hashlib.sha256).hexdigest()[:16]
    assert h != hmac.new(b'pbt', b'127.0.0.1', hashlib.sha256).hexdigest()[:16] and len(salt) >= 32


def test_idle_connection_is_closed_by_timeout(srv):
    """M14 (S7): з'єднання без запиту закривається за таймаутом (slowloris не тримає потік назавжди)."""
    s = srv(REQUEST_TIMEOUT='1')
    c = socket.create_connection(('127.0.0.1', s.port)); c.settimeout(6)
    t = time.monotonic()
    try:
        data = c.recv(10)
    except (ConnectionResetError, socket.timeout):
        data = None
    dt = time.monotonic() - t; c.close()
    assert data == b'' and dt < 4, (data, dt)                 # сервер сам закрив з'єднання


def test_health_reports_low_disk(srv):
    """M21: здоров'я справді міряє вільне місце: поріг вище за наявне → 503 disk:false."""
    s = srv(HEALTH_MIN_FREE_MB='1e12')
    try:
        urllib.request.urlopen(s.base + '/api/health'); assert False
    except urllib.error.HTTPError as e:
        assert e.code == 503 and json.loads(e.read()) == {'ok': False, 'db': True, 'disk': False}
    s.kill()
    s2 = srv()
    assert json.loads(urllib.request.urlopen(s2.base + '/api/health').read()) == {'ok': True, 'db': True, 'disk': True}


def test_hsts_only_for_https_forwarded_proto(srv):
    """M22: HSTS лише коли довірений проксі повідомив https; http і довільні значення — без HSTS."""
    s = srv(TRUST_PROXY='1')
    for proto, want in (('https', True), ('http', False), ('HTTPS ', False), ('', False)):
        _, h = _headers(s.base, '/', {'X-Forwarded-Proto': proto})
        assert ('Strict-Transport-Security' in h) is want, proto


def test_xff_trusted_only_from_loopback_peer(srv):
    """N4 (J): довіра до X-Forwarded-For — лише від loopback-піра (127.0.0.1/::1), навіть за TRUST_PROXY=1. Клієнт з іншої адреси
    (тут вихідна 127.0.0.2 — не 127.0.0.1) не може обрати собі ідентичність заголовком."""
    s = srv(TRUST_PROXY='1', RATE_LEAD_10MIN='1')

    def lead(xff, key, src):
        body = json.dumps(LEAD).encode()
        req = (f'POST /api/lead HTTP/1.1\r\nHost: 127.0.0.1:{s.port}\r\nOrigin: {s.base}\r\nContent-Type: application/json\r\n'
               f'Idempotency-Key: {key}\r\nX-Forwarded-For: {xff}\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n').encode() + body
        with socket.create_connection(('127.0.0.1', s.port), source_address=(src, 0)) as c:
            c.sendall(req); resp = b''
            while chunk := c.recv(4096): resp += chunk
        return int(resp.split(b' ', 2)[1])
    assert lead('203.0.113.7', 'k-n4-00000001', '127.0.0.2') == 201
    assert lead('198.51.100.9', 'k-n4-00000002', '127.0.0.2') == 429     # інший XFF, той самий не-loopback пір → та сама ідентичність
    assert lead('198.51.100.9', 'k-n4-00000003', '127.0.0.1') == 201     # від loopback-проксі XFF діє: новий клієнт


# ─── P14: HTTP Range для медіа (Safari/iOS без 206 не грає mp4; Chromium не перемотує) ──────────
def _get(base, path, extra=None, method='GET'):
    req = urllib.request.Request(base + path, headers=extra or {}, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


MEDIA = '/media/cine/karier-m.mp4'


def test_media_range_returns_exact_slice(srv):
    s = srv(); full = (ROOT / 'web' / MEDIA.lstrip('/')).read_bytes(); n = len(full)
    st, h, body = _get(s.base, MEDIA, {'Range': 'bytes=100-1099'})
    assert st == 206 and h['Content-Range'] == f'bytes 100-1099/{n}' and body == full[100:1100]
    assert h['Content-Length'] == '1000' and h['Accept-Ranges'] == 'bytes' and h['Content-Type'] == 'video/mp4'
    assert 'max-age=604800' in h['Cache-Control']
    st, h, body = _get(s.base, MEDIA, {'Range': 'bytes=-500'})                     # суфікс
    assert st == 206 and body == full[-500:] and h['Content-Range'] == f'bytes {n - 500}-{n - 1}/{n}'
    st, h, body = _get(s.base, MEDIA, {'Range': f'bytes={n - 10}-'})               # відкритий кінець
    assert st == 206 and body == full[-10:]
    st, h, body = _get(s.base, MEDIA, {'Range': f'bytes=0-{n + 999}'})            # кінець за файлом → обрізати
    assert st == 206 and body == full


def test_media_range_unsatisfiable_and_fallbacks(srv):
    s = srv(); full = (ROOT / 'web' / MEDIA.lstrip('/')).read_bytes(); n = len(full)
    st, h, body = _get(s.base, MEDIA, {'Range': f'bytes={n}-'})
    assert st == 416 and h['Content-Range'] == f'bytes */{n}' and body == b''
    for bad in ('bytes=0-1,5-9', 'items=0-9', 'bytes=-', 'bytes=9-1x'):              # кілька/чужі/зламані → увесь файл
        st, h, body = _get(s.base, MEDIA, {'Range': bad})
        assert (st, body) == (200, full), bad
    st, h, body = _get(s.base, MEDIA, {'Range': 'bytes=0-9', 'If-Range': 'Wed, 01 Jan 2020 00:00:00 GMT'})   # інша версія
    assert (st, body) == (200, full)
    st, h, _ = _get(s.base, MEDIA)
    lm = h['Last-Modified']
    st, h, body = _get(s.base, MEDIA, {'Range': 'bytes=0-9', 'If-Range': lm})
    assert (st, body) == (206, full[:10])
    st, h, body = _get(s.base, MEDIA, {'Range': 'bytes=0-9'}, method='HEAD')
    assert st == 206 and body == b'' and h['Content-Length'] == '10'
    st, _, _ = _get(s.base, '/media/cine/nemaye.mp4', {'Range': 'bytes=0-9'})
    assert st == 404


def test_media_range_rfc_edges(srv):
    """Аудит 2c9d850 (D4–D6): одиниця нечутлива до регістру; 5-3 → ігнор (200), не 416; If-Modified-Since ДО Range → 304;
    IMS порівнюється як дата; /media/../js/… не отримує тижневий кеш; HEAD 404 — без тіла."""
    s = srv(); full = (ROOT / 'web' / MEDIA.lstrip('/')).read_bytes()
    st, _, body = _get(s.base, MEDIA, {'Range': 'Bytes=0-9'})
    assert (st, body) == (206, full[:10])
    st, _, body = _get(s.base, MEDIA, {'Range': 'bytes=5-3'})
    assert (st, body) == (200, full)
    _, h, _ = _get(s.base, MEDIA); lm = h['Last-Modified']
    st, _, body = _get(s.base, MEDIA, {'Range': 'bytes=0-9', 'If-Modified-Since': lm})
    assert (st, body) == (304, b'')
    st, _, _ = _get(s.base, MEDIA, {'If-Modified-Since': 'Fri, 01 Jan 2100 00:00:00 GMT'})      # пізніша дата — теж 304
    assert st == 304
    st, _, body = _get(s.base, MEDIA, {'If-Modified-Since': 'Thu, 01 Jan 1970 00:00:00 GMT'})   # раніша — тіло
    assert (st, body) == (200, full)
    st, _, body = _get(s.base, MEDIA, {'If-Modified-Since': 'not-a-date'})
    assert (st, body) == (200, full)
    st, h, _ = _get(s.base, '/media/../js/site.js')
    assert st == 200 and 'max-age' not in (h['Cache-Control'] or '') and h['Accept-Ranges'] is None
    host, port = s.base.split('//')[1].split(':')                  # HEAD — сирим сокетом: urllib на HEAD тіло не читає й не бачить
    with socket.create_connection((host, int(port)), timeout=5) as c:
        c.sendall(b'HEAD /nemaye-takoi-storinky HTTP/1.0\r\nHost: x\r\n\r\n'); raw = b''
        while (chunk := c.recv(65536)):
            raw += chunk
    head, _, tail = raw.partition(b'\r\n\r\n')
    assert head.startswith(b'HTTP/1.0 404') and tail == b'', (head[:40], len(tail))


def test_media_symlink_out_of_web_is_404(srv, tmp_path):
    """Мутант аудиту M1: гілка /media/ перед in_web → symlink у web/media назовні віддавав файл. Тепер 404 (GET, HEAD, Range)."""
    s = srv(); secret = tmp_path / 'outside.mp4'; secret.write_bytes(b'TOP-SECRET-MEDIA' * 64)
    link = ROOT / 'web' / 'media' / 'cine' / 'zz_probe_out.mp4'
    try:
        link.symlink_to(secret)
        for hdr in ({}, {'Range': 'bytes=0-15'}):
            for method in ('GET', 'HEAD'):
                st, _, body = _get(s.base, '/media/cine/zz_probe_out.mp4', hdr, method=method)
                assert st == 404 and b'SECRET' not in body, (hdr, method, st)
    finally:
        link.unlink(missing_ok=True)
