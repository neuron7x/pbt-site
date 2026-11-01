"""Quantified Python-heap cardinality stress for the in-memory IP limiter.

Evidence is limited to the deterministic isolated-process Python heap; this
is NOT a server RSS, HTTP throughput or 30-minute soak certification.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_25000_distinct_identities_do_not_expand_active_rate_state(tmp_path):
    script = r'''
import gc
import importlib.util
import json
from pathlib import Path
import tracemalloc

path = Path('server/app.py').resolve()
spec = importlib.util.spec_from_file_location('pbt_memory_probe', path)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
assert app.RATE_IP_CAP == 32
tracemalloc.start()
baseline, _ = tracemalloc.get_traced_memory()
accepted = 0
for n in range(25000):
    accepted += bool(app.rate_ok(f'client-{n}', 'any'))
gc.collect()
current, peak = tracemalloc.get_traced_memory()
assert accepted == 25000, accepted
assert len(app._active_ips) == 32, len(app._active_ips)
assert len(app._hits) == 32, len(app._hits)
assert len(app._overflow) == 24968, len(app._overflow)
assert 'client-24999' in app._active_ips and 'client-0' not in app._active_ips
assert app.rate_ok('new-client-after-cap', 'any') is True
assert len(app._active_ips) == 32 and len(app._hits) == 32
assert peak - baseline < 8 * 1024 * 1024, peak - baseline
print(json.dumps({'attempted_distinct_identities': 25000,
                  'accepted_distinct_identities': accepted,
                  'tracked_active_ips': len(app._active_ips),
                  'tracked_buckets': len(app._hits),
                  'tracemalloc_peak_delta_bytes': peak - baseline,
                  'test_peak_heap_budget_bytes': 8 * 1024 * 1024,
                  'scope': 'isolated_python_heap_not_rss_or_http_soak'}))
'''
    env = {**os.environ, 'LEAD_DB': str(tmp_path / 'rate.db'),
           'IP_HASH_SALT': 'isolated-test', 'RATE_IP_CAP': '32',
           'RATE_ANY_10MIN': '100000', 'PYTHONDONTWRITEBYTECODE': '1'}
    done = subprocess.run([sys.executable, '-c', script], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=25, check=False)
    assert done.returncode == 0, done.stdout + done.stderr
    result = json.loads(done.stdout)
    assert result['accepted_distinct_identities'] == 25000
    assert result['tracked_buckets'] == 32
    assert result['tracemalloc_peak_delta_bytes'] < result['test_peak_heap_budget_bytes']


def test_bounded_overflow_recovers_only_after_the_whole_quota_window(tmp_path):
    """No lost history at saturation; identity capacity recovers after expiry."""
    script = r'''
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('pbt_rate_expiry_probe', Path('server/app.py'))
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
clock = [100000.0]
app.time.monotonic = lambda: clock[0]
assert app.rate_ok('a', 'any')
assert app.rate_ok('a', 'lead_day')
assert app.rate_ok('b', 'any')
assert app.rate_ok('c', 'any')
assert not app.rate_ok('d', 'any')  # 1 hot + 2 overflow identities
assert len(app._active_ips) == 1 and len(app._overflow) == 2
assert not app.rate_ok('a', 'lead_day')
clock[0] += 601
assert app.rate_ok('d', 'any')  # b/c expired, but a's daily limit did not
assert not app.rate_ok('a', 'lead_day')
clock[0] += 86400
assert app.rate_ok('a', 'lead_day')
assert len(app._active_ips) <= app.RATE_IP_CAP
assert len(app._overflow) <= app.RATE_OVERFLOW_CAP
'''
    env = {**os.environ, 'LEAD_DB': str(tmp_path / 'expiry.db'),
           'IP_HASH_SALT': 'isolated-test', 'RATE_IP_CAP': '1', 'RATE_OVERFLOW_CAP': '2',
           'RATE_LEAD_DAY': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    done = subprocess.run([sys.executable, '-c', script], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=10, check=False)
    assert done.returncode == 0, done.stdout + done.stderr


def test_wall_clock_steps_do_not_expire_or_reset_quota(tmp_path):
    script = r'''
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('pbt_rate_clock_probe', Path('server/app.py'))
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
wall, elapsed = [100000.0], [10000.0]
app.time.time = lambda: wall[0]
app.time.monotonic = lambda: elapsed[0]
assert app.rate_ok('a', 'any')
assert app.rate_ok('a', 'lead_day')
assert app.rate_ok('b', 'any')
wall[0] += 86401
assert not app.rate_ok('c', 'any'), 'forward wall-clock step prematurely freed capacity'
assert not app.rate_ok('a', 'lead_day'), 'forward wall-clock step reset quota'
wall[0] -= 86401
assert not app.rate_ok('a', 'lead_day'), 'backward wall-clock step reset quota'
elapsed[0] += 86400
assert app.rate_ok('c', 'any'), 'elapsed quota window did not expire'
assert app.rate_ok('a', 'lead_day'), 'elapsed daily quota did not expire'
'''
    env = {**os.environ, 'LEAD_DB': str(tmp_path / 'wall-clock.db'),
           'IP_HASH_SALT': 'isolated-test', 'RATE_IP_CAP': '1', 'RATE_OVERFLOW_CAP': '1',
           'RATE_LEAD_DAY': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    done = subprocess.run([sys.executable, '-c', script], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=10, check=False)
    assert done.returncode == 0, done.stdout + done.stderr


def test_quota_clock_is_read_after_acquiring_the_state_lock(tmp_path):
    """A waiting writer must not append an old timestamp behind a newer one."""
    script = r'''
import importlib.util
import threading
from pathlib import Path

spec = importlib.util.spec_from_file_location('pbt_rate_lock_clock_probe', Path('server/app.py'))
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
clock, read = [1000.0], threading.Event()
def monotonic():
    read.set()
    return clock[0]
app.time.monotonic = monotonic

for commit in (False, True):
    read.clear()
    started = threading.Event()
    errors = []
    def writer():
        started.set()
        try:
            if commit:
                app.rate_commit('a', 'lead')
            else:
                assert app.rate_ok('a', 'any')
        except BaseException as error:
            errors.append(error)

    with app._hits_lock:
        thread = threading.Thread(target=writer)
        thread.start()
        assert started.wait(3)
        assert not read.wait(0.3), 'clock read occurred before acquiring the quota lock'
        clock[0] += 601
    thread.join(timeout=3)
    assert not thread.is_alive() and not errors, errors
    assert read.is_set()
    bucket = 'lead' if commit else 'any'
    assert app._hits[('a', bucket)][-1] == clock[0]
'''
    env = {**os.environ, 'LEAD_DB': str(tmp_path / 'lock-clock.db'),
           'IP_HASH_SALT': 'isolated-test', 'PYTHONDONTWRITEBYTECODE': '1'}
    done = subprocess.run([sys.executable, '-c', script], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=10, check=False)
    assert done.returncode == 0, done.stdout + done.stderr
