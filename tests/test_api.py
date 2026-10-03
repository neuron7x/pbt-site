"""API заявок: серверна валідація, безпека (OWASP Input Validation / CSRF), зберігання."""
import json, urllib.error, urllib.request
from pathlib import Path
import pytest


def post(base, data=None, origin=True, ctype='application/json', raw=None):
    body = raw if raw is not None else json.dumps(data).encode()
    h = {'Content-Type': ctype}
    if origin is True:
        h['Origin'] = base
    elif origin:
        h['Origin'] = origin
    req = urllib.request.Request(base + '/api/lead', body, h, method='POST')
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


OK = {'type': 'rent', 'subject': 'Екскаватор JCB JS220LC', 'hours': '16', 'km': '40', 'place': 'Полтава, вул. Довженка, 2А', 'method': 'phone', 'contact': '067 123 45 67'}


def test_valid_lead_stored_normalized(server):
    code, j = post(server['base'], OK)
    assert code == 201 and j['ok'] and j['ref'].startswith('PBT-')


def test_csrf_origin_required(server):
    assert post(server['base'], OK, origin=None)[0] == 403
    assert post(server['base'], OK, origin='https://evil.example')[0] == 403


def test_content_type_and_size(server):
    assert post(server['base'], OK, ctype='text/plain')[0] == 415
    assert post(server['base'], raw=b'x' * 9000)[0] == 413
    assert post(server['base'], raw=b'{bad json')[0] == 400


def test_allowlists_and_semantics(server):
    code, j = post(server['base'], {**OK, 'type': 'hack', 'method': 'sms'})
    assert code == 422 and {'type', 'method'} <= set(j['fields'])
    code, j = post(server['base'], {'type': 'rent', 'method': 'telegram', 'contact': '@ab'})
    assert code == 422 and {'contact', 'subject'} <= set(j['fields'])
    code, j = post(server['base'], {**OK, 'type': 'material', 'subject': 'x'})
    assert code == 422 and 'subject' in j['fields']
    code, j = post(server['base'], {**OK, 'type': 'other', 'subject': '', 'comment': 'ок'})
    assert code == 422 and 'comment' in j['fields']
    code, j = post(server['base'], {**OK, 'hours': '0'})
    assert code == 422 and 'hours' in j['fields']
    code, j = post(server['base'], {**OK, 'hours': '5001'})
    assert code == 422 and 'hours' in j['fields']
    code, j = post(server['base'], {**OK, 'km': '-5'})
    assert code == 422 and 'km' in j['fields']
    code, j = post(server['base'], {**OK, 'date': '2020-01-01'})          # минуле
    assert code == 422 and 'date' in j['fields']
    code, j = post(server['base'], {**OK, 'date': '2027-02-30'})          # неіснуюча
    assert code == 422 and 'date' in j['fields']
    code, j = post(server['base'], {**OK, 'date': '2099-12-31'})
    assert code == 201
    code, j = post(server['base'], {**OK, 'comment': 'x' * 1001})
    assert code == 422 and 'comment' in j['fields']


def test_control_chars_stripped_and_stored_as_data(server):
    import sqlite3
    code, j = post(server['base'], {**OK, 'subject': '<script>alert(1)</script>', 'comment': 'a\u202eb\x00c'})
    assert code == 201
    row = sqlite3.connect(server['db']).execute('select payload from leads order by id desc limit 1').fetchone()
    d = json.loads(row[0])
    assert d['comment'] == 'abc' and d['contact'] == '+380671234567' and d['hours'] == 16 and d['km'] == 40
    assert d['subject'] == '<script>alert(1)</script>'          # зберігається як дані; екранування — на виході


def test_honeypot_silent(server):
    code, j = post(server['base'], {**OK, 'website': 'http://spam'})
    assert code == 200 and j['ref'] == 'PBT-000000'


def test_security_headers(server):
    h = urllib.request.urlopen(server['base'] + '/').headers
    assert "frame-ancestors 'none'" in h['Content-Security-Policy']
    assert h['X-Content-Type-Options'] == 'nosniff' and h['X-Frame-Options'] == 'DENY'


def test_public_config_has_no_internal_fields(server):
    c = json.loads(urllib.request.urlopen(server['base'] + '/api/config').read())
    assert '_status' not in c and c['brand']['name'] == 'ПБТ'


# ─── безпека сервера (аудит 25.09.2026: S1, S4, S5, S6) ───
def _get(base, path, headers=None):
    req = urllib.request.Request(base + path, headers=headers or {})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def test_S1_rate_limit_per_forwarded_client_not_global(tmp_path):
    """За локальним проксі ліміт рахується на клієнта з X-Forwarded-For, а не на спільний 127.0.0.1."""
    import os, socket, subprocess, sys, time
    from pathlib import Path
    s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
    env = {**os.environ, 'PORT': str(port), 'HOST': '127.0.0.1', 'LEAD_DB': str(tmp_path / 'l.db'), 'RATE_LEAD_10MIN': '3',
           'TELEGRAM_BOT_TOKEN': '', 'LEAD_WEBHOOK_URL': '', 'TRUST_PROXY': '1'}
    proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve().parent.parent / 'server' / 'app.py')], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f'http://127.0.0.1:{port}'
    for _ in range(100):
        try:
            urllib.request.urlopen(base + '/api/health'); break
        except Exception:  # noqa: BLE001
            time.sleep(.05)

    def lead(ip):
        h = {'Content-Type': 'application/json', 'Origin': base, 'X-Forwarded-For': ip}
        req = urllib.request.Request(base + '/api/lead', json.dumps({**OK, 'contact': '067 000 00 01'}).encode(), h, method='POST')
        try:
            with urllib.request.urlopen(req) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
    try:
        codes_a = [lead('203.0.113.7') for _ in range(5)]
        assert codes_a[:3] == [201] * 3 and 429 in codes_a  # один клієнт упирається в ліміт
        assert lead('198.51.100.9') == 201                  # інший клієнт — ні
    finally:
        proc.terminate(); proc.wait(5)


def test_S4_no_directory_listing(server):
    code, _, body = _get(server['base'], '/media/')
    assert code == 404 and b'Directory listing' not in body


def test_S5_csp_scripts_without_unsafe_inline(server):
    _, h, _ = _get(server['base'], '/')
    csp = h.get('Content-Security-Policy', '')
    script = next(p for p in csp.split(';') if p.strip().startswith('script-src'))
    assert "'unsafe-inline'" not in script and "'sha256-" in script


def test_S6_hsts_only_over_https(server):
    _, h, _ = _get(server['base'], '/')
    assert 'Strict-Transport-Security' not in h
    _, h, _ = _get(server['base'], '/', {'X-Forwarded-Proto': 'https'})
    assert h.get('Strict-Transport-Security', '').startswith('max-age=')


def test_no_files_outside_web(server):
    for p in ('/../.env', '/..%2f.env', '/../server/app.py', '/../data/leads.db', '/%2e%2e/config/business.json'):
        assert _get(server['base'], p)[0] == 404, p


def test_fuzz_lead_endpoint_never_5xx(server):
    """Властивість: будь-яке тіло (випадкові типи, юнікод, керівні символи, вкладеність, великі числа) → 2xx/4xx з JSON {ok}.
    Жодної 5xx і жодного збою обробника (відтворювано: seed = номер випадку)."""
    import random
    atoms = [None, True, 0, -1, 10**30, 1e308, float('nan'), '', ' ', 'a' * 5000, '\x00\x07‮⁦', '<script>alert(1)</script>',
             "'; DROP TABLE leads;--", '067 123 45 67', '+380671234567', '@user_name', 'https://copart.com/lot/1', 'javascript:alert(1)',
             'WBA3A5C51DF000000', '２０２０', '🚗' * 50, [], {}, [1, 2], {'a': {'b': [None]}}]
    keys = ['type', 'subject', 'hours', 'km', 'place', 'date', 'name', 'method', 'contact', 'comment', 'website', 'x' * 300]
    bad = []
    for seed in range(400):
        R = random.Random(seed)
        body = {k: (R.choice(['rent', 'material', 'transport', 'other', 'phone', 'telegram']) if R.random() < .3 else R.choice(atoms))
                for k in R.sample(keys, R.randint(0, len(keys)))}
        if R.random() < .1:
            body = R.choice(atoms)
        raw = json.dumps(body, allow_nan=True).encode()
        if len(raw) > 8000:
            raw = raw[:8000]
        try:
            code, j = post(server['base'], raw=raw)
        except Exception as e:  # noqa: BLE001 — обрив з'єднання = збій обробника
            bad.append((seed, 'обрив', type(e).__name__, raw[:120])); continue
        if code >= 500 or not isinstance(j, dict) or 'ok' not in j:
            bad.append((seed, code, str(j)[:80]))
    assert bad == [], bad[:5]


def test_O1_health_checks_real_storage(server):
    code, h, body = _get(server['base'], '/api/health')
    j = json.loads(body)
    assert code == 200 and j['ok'] is True and j['db'] is True and j['disk'] is True


def test_O2_backup_is_consistent_and_rotated(tmp_path):
    import os, sqlite3, subprocess, sys
    from pathlib import Path
    db = tmp_path / 'leads.db'
    with sqlite3.connect(db) as c:
        c.execute('CREATE TABLE leads(id INTEGER PRIMARY KEY, created TEXT, type TEXT, payload TEXT, ip_hash TEXT, ua TEXT, delivered TEXT)')
        c.executemany("INSERT INTO leads(created,type,payload) VALUES('t','rent','{}')", [()] * 5)
    env = {**os.environ, 'LEAD_DB': str(db), 'BACKUP_DIR': str(tmp_path / 'bk'), 'BACKUP_KEEP': '2'}
    script = Path(__file__).resolve().parent.parent / 'ops' / 'backup.py'
    for i in range(3):
        r = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True)
        assert r.returncode == 0 and 'заявок=5' in r.stdout, r.stdout + r.stderr
        import time; time.sleep(1.1)
    files = sorted((tmp_path / 'bk').glob('leads-*.db'))
    assert len(files) == 2                                   # ротація
    assert oct(files[-1].stat().st_mode)[-3:] == '600'       # лише власник
    with sqlite3.connect(files[-1]) as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok' and c.execute('SELECT count(*) FROM leads').fetchone()[0] == 5


def test_P12_text_assets_gzip_etag_and_no_escape(server):
    """P12: CSS/JS/HTML стиснуті gzip з Vary і ETag (304 на повтор); зображення не перестискаються; шлях поза web/ — 404."""
    import gzip
    base = server['base']
    code, h, body = _get(base, '/css/site.css', {'Accept-Encoding': 'gzip'})
    assert code == 200 and h.get('Content-Encoding') == 'gzip' and 'Accept-Encoding' in h.get('Vary', '')
    raw = gzip.decompress(body); assert b':root' in raw and len(body) < len(raw) * .5
    code2, h2, _ = _get(base, '/css/site.css', {'Accept-Encoding': 'gzip', 'If-None-Match': h['ETag']})
    assert code2 == 304
    code3, h3, _ = _get(base, '/media/logo/pbt-mark.png', {'Accept-Encoding': 'gzip'})
    assert code3 == 200 and 'Content-Encoding' not in h3
    code4, h4, b4 = _get(base, '/', {'Accept-Encoding': 'gzip'})
    assert code4 == 200 and h4.get('Content-Encoding') == 'gzip' and b'<html' in gzip.decompress(b4)[:400].lower()
    assert _get(base, '/../server/app.py', {'Accept-Encoding': 'gzip'})[0] == 404
    code5, h5, b5 = _get(base, '/css/site.css')                    # без Accept-Encoding — як раніше, без стиснення
    assert code5 == 200 and 'Content-Encoding' not in h5 and b':root' in b5


VECTORS = json.loads((Path(__file__).parent / 'contracts' / 'lead_vectors.json').read_text(encoding='utf-8'))['vectors']


@pytest.mark.parametrize('v', VECTORS, ids=lambda v: f"{v['field']}:{v['value']}")
def test_contract_vectors_server(server, v):
    """Спільний корпус (tests/contracts/lead_vectors.json): сервер — авторитетна сторона того самого контракту, що й site.js."""
    data = {**OK, 'type': v['type'], v['field']: v['value']}
    if v['field'] == 'contact':
        data['method'] = v['method']
    code, j = post(server['base'], data)
    assert (v['field'] not in j.get('fields', {})) is v['valid'], (code, j)
    if v['valid']:
        assert code == 201, (code, j)


def test_S13_static_root_containment_symlinks_and_traversal(server, tmp_path):
    """Реальний шлях файлу мусить лежати в web/: symlink назовні → 404 (GET і HEAD, звичайний і gzip-шлях); symlink усередину — дозволено;
    сусідній каталог з тим самим префіксом (web_x) — не нащадок web/."""
    web = Path(__file__).resolve().parent.parent / 'web'
    secret = tmp_path / 'outside.txt'; secret.write_text('TOP-SECRET-OUTSIDE')
    sib = web.parent / 'web_s13_probe'; sib.mkdir(exist_ok=True); (sib / 'f.css').write_text('SIBLING')
    links = {'s13_out.txt': secret, 's13_out.css': secret, 's13_sib.css': sib / 'f.css', 's13_in.css': web / 'css' / 'fonts.css', 's13_dir': tmp_path}
    try:
        for name, target in links.items():
            (web / name).symlink_to(target)
        for p in ('/s13_out.txt', '/s13_out.css', '/s13_sib.css', '/s13_dir/outside.txt'):
            for h in ({}, {'Accept-Encoding': 'gzip'}):
                code, _, body = _get(server['base'], p, h)
                assert code == 404 and b'SECRET' not in body and b'SIBLING' not in body, (p, h, code)
            req = urllib.request.Request(server['base'] + p, method='HEAD')
            try:
                urllib.request.urlopen(req); assert False, p
            except urllib.error.HTTPError as e:
                assert e.code == 404, p
        assert _get(server['base'], '/s13_in.css')[0] == 200
        assert _get(server['base'], '/css/fonts.css')[0] == 200 and _get(server['base'], '/media/logo/pbt-mark.png')[0] == 200
        for p in ('/..%2F..%2Fserver%2Fapp.py', '/%2e%2e%2f%2e%2e/config/business.json', '/css/../../server/app.py', '/./../.env', '//etc/passwd'):
            code, _, body = _get(server['base'], p)
            assert code == 404 or b'import' not in body, p
            assert b'root:' not in body and b'def main' not in body, p
    finally:
        for name in links:
            (web / name).unlink(missing_ok=True)
        (sib / 'f.css').unlink(missing_ok=True); sib.rmdir()
