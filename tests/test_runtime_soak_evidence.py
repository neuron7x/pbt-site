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
        'schema': 'pbt-soak-evidence-v1',
        'profile': 'smoke', 'source_sha': head, 'status': 'PASS', 'violations': [],
        'accepted_leads': n, 'observed_duration_s': cfg['smoke']['minimum_duration_s'],
        'api_latency_samples_ms': [1.0] * n, 'api_p99_ms': 1.0,
        'rss_sample_epochs_kib': [[1024], [1280]],
        'child_rss_sample_epochs_kib': [[512], [0]],
        'child_process_sample_epochs': [[1], [0]],
        'tree_vm_rss_sum_peak_kib': 1536,
        'observed_child_processes_peak': 1,
        'resource_scope': 'sampled_server_plus_descendants_sum_vm_rss_not_cgroup_peak',
        'rss_peak_kib': 1280, 'rss_growth_max_kib': 0,
        'threads_peak': 4, 'pending_outbox_peak': 2,
        'process_crash_and_restart': True, 'backup_checkpoints': 2,
        'drain_elapsed_s': 1, 'final_sqlite_integrity': 'ok',
        'outbox': {'leads': n, 'pending': 0, 'delivered': n, 'failed': 0},
        'crm': {'invalid_hmac': 0, 'invalid_payloads': 0,
                'expected_crash_aborts': 0, 'unexpected_transport_aborts': 0,
                'observed_distinct_leads': n, 'total_webhook_attempts': n,
                'http_status_counts': {'200': n}},
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


def test_verifier_rejects_fabricated_child_memory_peak_and_missing_sample():
    """Mutating either side of process-tree evidence must not be accepted."""
    import pytest
    from tools.verify_soak_evidence import verify
    budget = json.loads((ROOT / 'config/runtime-soak-budgets.json').read_text())
    head = 'b' * 40
    n = budget['smoke']['minimum_accepted']
    report = {
        'schema': 'pbt-soak-evidence-v1',
        'profile': 'smoke', 'source_sha': head, 'status': 'PASS', 'violations': [],
        'accepted_leads': n, 'observed_duration_s': 10,
        'api_latency_samples_ms': [1.] * n, 'api_p99_ms': 1.,
        'rss_sample_epochs_kib': [[1024, 1050], [1200, 1300]],
        'child_rss_sample_epochs_kib': [[500, 400], [0, 600]],
        'child_process_sample_epochs': [[1, 1], [0, 1]],
        'tree_vm_rss_sum_peak_kib': 1900,
        'observed_child_processes_peak': 1,
        'resource_scope': 'sampled_server_plus_descendants_sum_vm_rss_not_cgroup_peak',
        'rss_peak_kib': 1300, 'rss_growth_max_kib': 100,
        'threads_peak': 4, 'pending_outbox_peak': 2,
        'process_crash_and_restart': True, 'backup_checkpoints': 2,
        'drain_elapsed_s': 1, 'final_sqlite_integrity': 'ok',
        'outbox': {'leads': n, 'pending': 0, 'delivered': n, 'failed': 0},
        'crm': {'invalid_hmac': 0, 'invalid_payloads': 0, 'expected_crash_aborts': 0,
                'unexpected_transport_aborts': 0, 'observed_distinct_leads': n,
                'total_webhook_attempts': n, 'http_status_counts': {'200': n}},
        'field_inp': 'NOT_MEASURED', 'scope': 'synthetic_local_http_sqlite_not_production'
    }
    assert verify(report, budget, head)
    import copy
    forged_peak = copy.deepcopy(report)
    forged_peak['tree_vm_rss_sum_peak_kib'] = 1300
    with pytest.raises(ValueError):
        verify(forged_peak, budget, head)
    missing_child = copy.deepcopy(report)
    missing_child['child_rss_sample_epochs_kib'][0].pop()
    with pytest.raises(ValueError):
        verify(missing_child, budget, head)
    impossible_child = copy.deepcopy(report)
    impossible_child['child_process_sample_epochs'][0][0] = -1
    with pytest.raises(ValueError):
        verify(impossible_child, budget, head)


def test_verifier_rejects_coherent_report_over_the_latency_budget():
    """Raw samples and summary agree with each other; only the predeclared limit can catch this."""
    import copy
    import pytest
    from tools.verify_soak_evidence import verify

    head = 'a' * 40
    cfg = json.loads((ROOT / 'config/runtime-soak-budgets.json').read_text())
    n = cfg['smoke']['minimum_accepted']
    over = float(cfg['budgets']['maximum_p99_lead_ms'] + 1)
    report = {
        'schema': 'pbt-soak-evidence-v1',
        'profile': 'smoke', 'source_sha': head, 'status': 'PASS', 'violations': [],
        'accepted_leads': n, 'observed_duration_s': cfg['smoke']['minimum_duration_s'],
        'api_latency_samples_ms': [over] * n, 'api_p99_ms': over,
        'rss_sample_epochs_kib': [[1024], [1280]],
        'child_rss_sample_epochs_kib': [[512], [0]],
        'child_process_sample_epochs': [[1], [0]],
        'tree_vm_rss_sum_peak_kib': 1536, 'observed_child_processes_peak': 1,
        'resource_scope': 'sampled_server_plus_descendants_sum_vm_rss_not_cgroup_peak',
        'rss_peak_kib': 1280, 'rss_growth_max_kib': 0,
        'threads_peak': 4, 'pending_outbox_peak': 2,
        'process_crash_and_restart': True, 'backup_checkpoints': 2,
        'drain_elapsed_s': 1, 'final_sqlite_integrity': 'ok',
        'outbox': {'leads': n, 'pending': 0, 'delivered': n, 'failed': 0},
        'crm': {'invalid_hmac': 0, 'invalid_payloads': 0,
                'expected_crash_aborts': 0, 'unexpected_transport_aborts': 0,
                'observed_distinct_leads': n, 'total_webhook_attempts': n,
                'http_status_counts': {'200': n}},
        'field_inp': 'NOT_MEASURED', 'scope': 'synthetic_local_http_sqlite_not_production',
    }
    healthy = copy.deepcopy(report)
    healthy.update(api_latency_samples_ms=[1.0] * n, api_p99_ms=1.0)
    assert verify(healthy, cfg, head), 'The complete control must pass every later invariant.'
    with pytest.raises(ValueError, match='latency_provenance_or_budget'):
        verify(copy.deepcopy(report), cfg, head)
