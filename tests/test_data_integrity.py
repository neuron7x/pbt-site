"""INV-01/02/04: referential integrity, atomic migration, atomic acceptance under process death."""
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.request

import pytest

from test_leads import LEAD, Srv, _port, srv  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / 'tests' / 'harness' / 'server_cut.py'


def _app_probe(db, code):
    """Run code against an imported server module, isolated by subprocess and LEAD_DB."""
    prelude = ('import importlib.util,sys,json,sqlite3\n'
               f"s=importlib.util.spec_from_file_location('app',{str(ROOT / 'server/app.py')!r})\n"
               "app=importlib.util.module_from_spec(s);sys.modules['app']=app;s.loader.exec_module(app)\n")
    env = {**os.environ, 'LEAD_DB': str(db), 'DELIVERY_WORKER': '0', 'MIGRATE_BOOT_ATTEMPTS': '1'}
    return subprocess.run([sys.executable, '-c', prelude + code], env=env, capture_output=True,
                          text=True, timeout=30)


def _legacy_db(path, orphan=False):
    """Schema as shipped before idempotency/outbox columns existed, with one real lead."""
    with sqlite3.connect(path) as c:
        c.execute('''CREATE TABLE leads(id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT NOT NULL,
                     type TEXT NOT NULL, payload TEXT NOT NULL, ip_hash TEXT, ua TEXT, delivered TEXT)''')
        c.execute("INSERT INTO leads(created,type,payload) VALUES('2026-01-01T00:00:00+00:00','rent','{}')")
        if orphan:
            c.execute('''CREATE TABLE outbox(id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL REFERENCES leads(id), channel TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
                next_at REAL NOT NULL DEFAULT 0, last_at REAL, last_error TEXT, delivered_at TEXT,
                UNIQUE(lead_id, channel))''')
            c.execute("INSERT INTO outbox(lead_id, channel) VALUES(777, 'webhook')")


def _schema(path):
    with sqlite3.connect(path) as c:
        return sorted(tuple(r) for r in c.execute('SELECT type,name,sql FROM sqlite_master'))


# ─── DB-01 ───────────────────────────────────────────────
def test_server_connection_enforces_foreign_keys_and_rejects_orphan(tmp_path):
    r = _app_probe(tmp_path / 'l.db', '''
c = app.db()
print(c.execute('PRAGMA foreign_keys').fetchone()[0], c.execute('PRAGMA synchronous').fetchone()[0])
try:
    c.execute("INSERT INTO outbox(lead_id, channel) VALUES(424242, 'webhook')")
    print('ACCEPTED')
except sqlite3.IntegrityError:
    print('REJECTED')
''')
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ['1', '2', 'REJECTED']


def test_outbox_insert_inside_real_acceptance_path_keeps_fk_clean(srv):
    s = srv(LEAD_WEBHOOK_URL='http://127.0.0.1:9/hook', LEAD_WEBHOOK_SECRET='k', DELIVERY_WORKER='0')
    assert s.post(LEAD, 'k-fk-clean-01')[0] == 201
    with sqlite3.connect(s.db) as c:
        assert c.execute('PRAGMA foreign_key_check').fetchall() == []
        assert c.execute('SELECT count(*) FROM outbox').fetchone() == (1,)


# ─── DB-02 ───────────────────────────────────────────────
def test_migration_failure_rolls_back_every_schema_write_then_retry_converges(tmp_path):
    db = tmp_path / 'legacy.db'
    _legacy_db(db)
    before = _schema(db)
    prelude = ('import importlib.util,sys,sqlite3\n'
               'real=sqlite3.connect\n'
               'class C(sqlite3.Connection):\n'
               '    def execute(self, sql, *a):\n'
               "        if 'CREATE TABLE IF NOT EXISTS runtime_heartbeat' in sql:\n"
               "            raise sqlite3.OperationalError('injected migration failure')\n"
               '        return super().execute(sql, *a)\n'
               "sqlite3.connect=lambda *a, **k: real(*a, **{'factory': C, **k})\n"
               f"s=importlib.util.spec_from_file_location('app',{str(ROOT / 'server/app.py')!r})\n"
               "app=importlib.util.module_from_spec(s);sys.modules['app']=app;s.loader.exec_module(app)\n"
               "print('schema_ok', app._schema_ok.is_set())\n")
    env = {**os.environ, 'LEAD_DB': str(db), 'MIGRATE_BOOT_ATTEMPTS': '1'}
    r = subprocess.run([sys.executable, '-c', prelude], env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    assert 'schema_ok False' in r.stdout
    assert _schema(db) == before, 'partial migration persisted after injected failure'
    assert _app_probe(db, "print(app._schema_ok.is_set())").stdout.strip() == 'True'
    migrated = _schema(db)
    assert _app_probe(db, "print(app._schema_ok.is_set())").stdout.strip() == 'True'
    assert _schema(db) == migrated, 'repeated migration is not idempotent'
    with sqlite3.connect(db) as c:
        assert c.execute('SELECT count(*) FROM leads').fetchone() == (1,)


def test_legacy_orphan_is_reported_never_repaired_and_never_lost(tmp_path, srv):
    db = tmp_path / 'db0.db'
    _legacy_db(db, orphan=True)
    s = Srv(db, DELIVERY_WORKER='0')
    try:
        assert s.post(LEAD, 'k-after-orphan-1')[0] == 201  # Unrelated intake continues.
        rows = s.rows('SELECT lead_id, status FROM outbox')
        assert (777, 'pending') in rows, 'orphan silently repaired or deleted'
        log = (ROOT / 'data' / 'server.log').read_text(encoding='utf-8', errors='replace')
        assert re.search(r'legacy foreign key violations=1 table=outbox', log)
    finally:
        s.kill()
    report = subprocess.run([sys.executable, str(ROOT / 'ops/outbox_health.py'), '--db', str(db),
                             '--max-pending-age-s', '60'], capture_output=True, text=True, timeout=15)
    assert report.returncode == 2 and json.loads(report.stdout)['reason'] == 'outbox_integrity'


def test_corrupt_database_does_not_take_down_static_site(tmp_path):
    db = tmp_path / 'corrupt.db'
    db.write_bytes(b'this is not a sqlite database' * 200)
    s = Srv(db, DELIVERY_WORKER='0', MIGRATE_BOOT_ATTEMPTS='1')
    try:
        with urllib.request.urlopen(s.base + '/', timeout=5) as r:
            assert r.status == 200
        assert s.post(LEAD, 'k-corrupt-00001')[0] == 503
    finally:
        s.kill()


# ─── DB-03 ───────────────────────────────────────────────
def _server_process(db, port, **env):
    e = {**os.environ, 'PORT': str(port), 'HOST': '127.0.0.1', 'LEAD_DB': str(db), 'RATE_ANY_10MIN': '100000',
         'RATE_LEAD_10MIN': '100000', 'RATE_LEAD_DAY': '100000', 'TELEGRAM_BOT_TOKEN': '', 'LEAD_WEBHOOK_URL': '',
         'LEAD_WEBHOOK_SECRET': '', 'DELIVERY_WORKER': '0', **env}
    p = subprocess.Popen([sys.executable, str(HARNESS)], env=e, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health', timeout=.5)
            return p
        except urllib.error.HTTPError:
            return p
        except Exception:  # noqa: BLE001
            time.sleep(.05)
    p.kill()
    raise RuntimeError('harness server did not start')


def _post(port, body, key):
    base = f'http://127.0.0.1:{port}'
    req = urllib.request.Request(base + '/api/lead', json.dumps(body).encode(),
                                 {'Content-Type': 'application/json', 'Origin': base, 'Idempotency-Key': key}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')
    except OSError as e:
        return None, {'transport': type(e).__name__}


def test_same_key_across_processes_yields_one_lead_and_conflict_is_not_replacement(tmp_path):
    db = tmp_path / 'multi.db'
    ports = [_port(), _port()]
    procs = [_server_process(db, p, PBT_ALLOW_SECOND_SERVER='1') for p in ports]
    try:
        with ThreadPoolExecutor(16) as pool:
            res = list(pool.map(lambda i: _post(ports[i % 2], LEAD, 'k-linearizable-1'), range(32)))
        assert {r[0] for r in res} == {201}
        assert len({r[1]['ref'] for r in res}) == 1
        assert sum('replayed' not in r[1] for r in res) == 1
        other = {**LEAD, 'subject': 'Інша техніка'}
        assert _post(ports[0], other, 'k-linearizable-1')[0] == 409
        with sqlite3.connect(db) as c:
            assert c.execute('SELECT count(*) FROM leads').fetchone() == (1,)
            assert json.loads(c.execute('SELECT payload FROM leads').fetchone()[0])['subject'] == LEAD['subject']
    finally:
        for p in procs:
            p.kill(); p.wait(5)


# ─── DB-04 ───────────────────────────────────────────────
@pytest.mark.parametrize('cut,committed', [
    ('before_begin', False), ('after_insert', False), ('after_outbox', False),
    ('before_commit', False), ('after_commit', True), ('before_reply', True),
])
def test_process_death_at_each_acceptance_cutpoint(tmp_path, cut, committed):
    """No 201 without a durable lead+outbox; retry after restart reaches the same logical lead."""
    db = tmp_path / 'cut.db'
    port = _port()
    hook = {'LEAD_WEBHOOK_URL': 'http://127.0.0.1:9/hook', 'LEAD_WEBHOOK_SECRET': 'k'}
    p = _server_process(db, port, PBT_CUT=cut, **hook)
    try:
        status, _ = _post(port, LEAD, 'k-cutpoint-0001')
        assert p.wait(10) == -9, 'cutpoint was not reached: harness exercised nothing'
        assert status is None, f'client observed {status} before the crash at {cut}'
    finally:
        if p.poll() is None:
            p.kill(); p.wait(5)
    with sqlite3.connect(db) as c:   # Opening recovers any hot journal, as a restart would.
        assert c.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        leads = c.execute('SELECT count(*) FROM leads').fetchone()[0]
        outbox = c.execute('SELECT count(*) FROM outbox').fetchone()[0]
    assert (leads, outbox) == ((1, 1) if committed else (0, 0)), 'partial or lost acceptance state'
    port2 = _port()
    p2 = _server_process(db, port2, **hook)
    try:
        status, body = _post(port2, LEAD, 'k-cutpoint-0001')
        assert status == 201 and body['ref'] == 'PBT-000001'
        assert body.get('replayed', False) is committed
    finally:
        p2.kill(); p2.wait(5)
    with sqlite3.connect(db) as c:
        assert c.execute('SELECT count(*) FROM leads').fetchone() == (1,)
        assert c.execute('SELECT count(*) FROM outbox').fetchone() == (1,)
        assert c.execute('PRAGMA foreign_key_check').fetchall() == []


def test_disk_full_during_accept_is_500_with_no_partial_state(tmp_path):
    """RLIMIT_FSIZE makes SQLite's own file writes fail like a full disk (EFBIG -> SQLITE_FULL)."""
    db = tmp_path / 'full.db'
    s = Srv(db, DELIVERY_WORKER='0')
    assert s.post(LEAD, 'k-disk-before-1')[0] == 201
    s.kill()
    size = db.stat().st_size
    port = _port()
    limiter = (f"import resource,runpy,sys,signal\nsignal.signal(signal.SIGXFSZ, signal.SIG_IGN)\n"
               f"import importlib.util\ns=importlib.util.spec_from_file_location('app',{str(ROOT/'server/app.py')!r})\n"
               "app=importlib.util.module_from_spec(s);sys.modules['app']=app;s.loader.exec_module(app)\n"
               f"resource.setrlimit(resource.RLIMIT_FSIZE,({size},{size}))\n"
               "app.main()\n")
    env = {**os.environ, 'PORT': str(port), 'HOST': '127.0.0.1', 'LEAD_DB': str(db), 'DELIVERY_WORKER': '0',
           'RATE_ANY_10MIN': '10000', 'RATE_LEAD_10MIN': '10000', 'RATE_LEAD_DAY': '10000'}
    p = subprocess.Popen([sys.executable, '-c', limiter], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=.5)
                break
            except Exception:  # noqa: BLE001
                time.sleep(.05)
        big = {**LEAD, 'comment': 'х' * 900}
        statuses = [_post(port, big, f'k-disk-full-{i:04d}')[0] for i in range(12)]
        assert 500 in statuses, statuses
    finally:
        p.kill(); p.wait(5)
    with sqlite3.connect(db) as c:
        assert c.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        ids = c.execute('SELECT id FROM leads ORDER BY id').fetchall()
        n_outbox = c.execute('SELECT count(*) FROM outbox').fetchone()[0]
    assert n_outbox == 0
    # Exactly the responses that were 201 are present: none lost, none ghost.
    assert len(ids) == 1 + statuses.count(201)
