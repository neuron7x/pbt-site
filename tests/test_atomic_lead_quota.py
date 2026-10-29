"""Deterministic real-socket falsification of the lead-quota check/commit race.

A barrier after the first read-only quota check forces eight concurrent
requests through the vulnerable check-then-write window. The SQLite lock must
recheck the limit and charge it before allowing the next SQLite transaction.
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
original_rate_ok = app.rate_ok

def interleaved_rate_ok(ip, *buckets, commit=True):
    allowed = original_rate_ok(ip, *buckets, commit=commit)
    if not commit and buckets == ('lead', 'lead_day'):
        with lock:
            first_checks[0] += 1
            initial = first_checks[0] <= 8
        if initial:
            barrier.wait(timeout=10)
    return allowed

app.rate_ok = interleaved_rate_ok
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
