"""A forged PASS label must not bypass the independent soak-evidence verifier."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def test_verifier_rejects_missing_measured_samples_even_when_status_says_pass(tmp_path):
    report = tmp_path / 'fake.json'
    report.write_text(json.dumps({
        'profile': 'soak', 'status': 'PASS', 'violations': [],
        'source_sha': 'a' * 40,
        'accepted_leads': 5000, 'observed_duration_s': 1900,
        'api_latency_samples_ms': [],
        'api_p99_ms': 1,
    }))
    p = subprocess.run([
        sys.executable, str(ROOT / 'tools/verify_soak_evidence.py'),
        '--report', str(report), '--expected-head', 'a' * 40
    ], cwd=ROOT, text=True, capture_output=True, timeout=10)
    assert p.returncode != 0 and 'FAIL' in p.stderr
