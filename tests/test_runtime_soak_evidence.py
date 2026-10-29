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


def test_verifier_rejects_forged_success_for_crm_integrity_and_crash_aborts():
    import copy
    import pytest
    from tools.verify_soak_evidence import verify

    head = 'a' * 40
    cfg = json.loads((ROOT / 'config/runtime-soak-budgets.json').read_text())
    n = cfg['smoke']['minimum_accepted']
    report = {
        'profile': 'smoke', 'source_sha': head, 'status': 'PASS', 'violations': [],
        'accepted_leads': n, 'observed_duration_s': cfg['smoke']['minimum_duration_s'],
        'api_latency_samples_ms': [1.0] * n, 'api_p99_ms': 1.0,
        'rss_sample_epochs_kib': [[1024], [1280]],
        'rss_peak_kib': 1280, 'rss_growth_max_kib': 0,
        'threads_peak': 4, 'pending_outbox_peak': 2,
        'process_crash_and_restart': True, 'backup_checkpoints': 2,
        'drain_elapsed_s': 1, 'final_sqlite_integrity': 'ok',
        'outbox': {'leads': n, 'pending': 0, 'delivered': n, 'failed': 0},
        'crm': {'invalid_hmac': 0, 'invalid_payloads': 0,
                'expected_crash_aborts': 0, 'unexpected_transport_aborts': 0,
                'observed_distinct_leads': n},
        'field_inp': 'NOT_MEASURED',
        'scope': 'synthetic_local_http_sqlite_not_production',
    }
    assert verify(report, cfg, head)
    for key, value in (('invalid_hmac', 1), ('invalid_payloads', 1),
                       ('unexpected_transport_aborts', 1), ('expected_crash_aborts', 5)):
        corrupted = copy.deepcopy(report)
        corrupted['crm'][key] = value
        with pytest.raises(ValueError):
            verify(corrupted, cfg, head)
    missing = copy.deepcopy(report)
    del missing['crm']['unexpected_transport_aborts']
    with pytest.raises(KeyError):
        verify(missing, cfg, head)
