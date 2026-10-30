"""Deterministic real-socket falsification of the lead-quota check/commit race.

A barrier after the initial idempotency lookup (after that lookup releases
_db_lock) brings eight distinct keyed requests to the quota admission boundary.
Never wait at a multi-request barrier while holding the SQLite serialization
lock: the old scheduler caused false HTTP 500 errors and a broken test.
Run in a separate interpreter to isolate server import side effects.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_same_ip_parallel_distinct_leads_never_exceed_quota(tmp_path):
    script = r'''
import importlib.util, json, sqlite3, threading, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

spec = importlib.util.spec_from_file_location('pbt_quota_race_probe', Path('server/app.py'))
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
assert app._schema_ok.is_set()

barrier = threading.Barrier(8)
lock = threading.Lock()
first_checks = [0]
original_replay = app.Handler.idem_replay

def synchronize_pre_admission(self, idem, payload_hash):
    # The original lookup returns after releasing _db_lock. Synchronize
    # distinct keys here, never from rate_ok() inside the write transaction.
    replay = original_replay(self, idem, payload_hash)
    if replay is None and idem.startswith('k-quota-race-'):
        with lock:
            first_checks[0] += 1
        barrier.wait(timeout=10)
    return replay

app.Handler.idem_replay = synchronize_pre_admission
class SocketServer(app.Server):
    request_queue_size = 64
server = SocketServer(('127.0.0.1', 0), app.Handler, max_conn=32, slot_wait=5)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
url = f'http://127.0.0.1:{server.server_address[1]}'
lead = {'type':'rent','subject':'Екскаватор','method':'phone','contact':'0671234567','hours':'16'}

def submit(i):
    req = urllib.request.Request(url + '/api/lead', json.dumps(lead).encode(),
        {'Origin':url, 'Content-Type':'application/json',
         'Idempotency-Key':f'k-quota-race-{i:08d}'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            response.read()
            return response.status
    except urllib.error.HTTPError as exc:
        exc.read()
        return exc.code

try:
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(submit, range(8)))
    with sqlite3.connect(app.DB) as db:
        n = db.execute('SELECT count(*) FROM leads').fetchone()[0]
    assert first_checks[0] >= 8, first_checks
    assert statuses.count(201) == n == 1, (statuses, n)
    assert statuses.count(429) == 7, statuses
    print(json.dumps({'concurrent':8,'quota':1,'persisted':n,'statuses':statuses,
                      'scope':'single_process_real_socket_scheduled_race'}))
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=4)
'''
    env = {**os.environ, 'LEAD_DB': str(tmp_path / 'quota-race.db'),
           'IP_HASH_SALT': 'isolated-quota-race-test', 'DELIVERY_WORKER': '0',
           'TELEGRAM_BOT_TOKEN': '', 'TELEGRAM_CHAT_ID': '',
           'LEAD_WEBHOOK_URL': '', 'LEAD_WEBHOOK_SECRET': '',
           'RATE_LEAD_10MIN': '1', 'RATE_LEAD_DAY': '1',
           'RATE_ANY_10MIN': '1000', 'PYTHONDONTWRITEBYTECODE': '1'}
    result = subprocess.run([sys.executable, '-c', script], cwd=ROOT,
                            env=env, capture_output=True, text=True,
                            timeout=35, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    record = json.loads(result.stdout.strip())
    assert record['persisted'] == record['quota'] == 1


def test_same_key_scheduled_replay_or_conflict_before_quota(tmp_path):
    """Real HTTP concurrency: a stale initial lookup must not convert 201/409 into 429.

    This test interposes only at the pre-existing idempotency lookup and rate
    charge. All application HTTP, SQLite and transaction code is unmodified.
    An eight-client barrier ensures every initial lookup observes no row;
    only one request may commit before the others resume. The uncorrected
    keyed fast-path fails deterministically (seven false 429 responses).
    """
    script = r'''
import importlib.util, json, sqlite3, threading, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

spec = importlib.util.spec_from_file_location('pbt_idempotency_race_probe', Path('server/app.py'))
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
assert app._schema_ok.is_set()

key = 'k-scheduled-idempotency-2026'
barrier = threading.Barrier(8)
charged = threading.Event()
original_replay = app.Handler.idem_replay
original_charge = app.rate_commit

def interleaved_replay(self, idem, ph):
    result = original_replay(self, idem, ph)
    if idem == key and result is None:
        index = barrier.wait(timeout=12)
        if index != 0:
            assert charged.wait(timeout=12), 'leader never charged durable lead'
    return result

def charge_and_release(ip, *buckets):
    result = original_charge(ip, *buckets)
    if buckets == ('lead', 'lead_day'):
        charged.set()
    return result

app.Handler.idem_replay = interleaved_replay
app.rate_commit = charge_and_release

class SocketServer(app.Server):
    request_queue_size = 64

server = SocketServer(('127.0.0.1', 0), app.Handler, max_conn=32, slot_wait=5)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
url = f'http://127.0.0.1:{server.server_address[1]}'
lead = {'type':'rent', 'subject':'Екскаватор', 'method':'phone',
        'contact':'0671234567', 'hours':'16'}

def submit(i):
    req = urllib.request.Request(
        url + '/api/lead', json.dumps(lead, ensure_ascii=False).encode(),
        {'Origin':url, 'Content-Type':'application/json',
         'Idempotency-Key':key}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())

try:
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(submit, range(8)))
    with sqlite3.connect(app.DB) as conn:
        rows = conn.execute('SELECT count(*) FROM leads').fetchone()[0]
    statuses = [code for code, _ in responses]
    assert statuses.count(201) == 8, responses
    assert statuses.count(429) == statuses.count(409) == 0, responses
    assert len({body['ref'] for _, body in responses}) == 1, responses
    assert sum(body.get('replayed') is True for _, body in responses) == 7
    assert rows == 1, rows
    # The same durable key with a different valid payload must still be 409,
    # not a quota response even though the quota is now exhausted.
    conflict = dict(lead, subject='Інший екскаватор')
    req = urllib.request.Request(
        url + '/api/lead', json.dumps(conflict, ensure_ascii=False).encode(),
        {'Origin':url, 'Content-Type':'application/json',
         'Idempotency-Key':key}, method='POST')
    try:
        urllib.request.urlopen(req, timeout=10)
        raise AssertionError('conflicting payload unexpectedly accepted')
    except urllib.error.HTTPError as exc:
        assert exc.code == 409, exc.code
        exc.read()
    print(json.dumps({'concurrent':8,'quota':1,'persisted':rows,
                      'statuses':statuses,'conflict':409}))
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=4)
'''
    env = {**os.environ, 'LEAD_DB': str(tmp_path / 'same-key-race.db'),
           'IP_HASH_SALT': 'isolated-idempotency-race-test',
           'DELIVERY_WORKER': '0', 'TELEGRAM_BOT_TOKEN': '',
           'TELEGRAM_CHAT_ID': '', 'LEAD_WEBHOOK_URL': '',
           'LEAD_WEBHOOK_SECRET': '', 'RATE_LEAD_10MIN': '1',
           'RATE_LEAD_DAY': '1', 'RATE_ANY_10MIN': '1000',
           'PYTHONDONTWRITEBYTECODE': '1'}
    result = subprocess.run([sys.executable, '-c', script], cwd=ROOT,
                            env=env, capture_output=True, text=True,
                            timeout=45, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    record = json.loads(result.stdout.strip())
    assert record['persisted'] == 1 and record['concurrent'] == 8
    assert record['statuses'] == [201] * 8 and record['conflict'] == 409
