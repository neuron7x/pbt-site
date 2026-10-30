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
