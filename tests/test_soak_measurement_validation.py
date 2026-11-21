"""Malformed measurements must never certify a synthetic soak as successful."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.meta_evidence_gate import verify_soak
from tools.verify_soak_evidence import verify

ROOT = Path(__file__).resolve().parents[1]
HEAD = 'a' * 40


@pytest.fixture
def evidence():
    budget = json.loads((ROOT / 'config/runtime-soak-budgets.json').read_text())
    accepted = budget['soak']['minimum_accepted']
    report = {
        'schema': 'pbt-soak-evidence-v1', 'source_sha': HEAD, 'profile': 'soak',
        'status': 'PASS', 'violations': [], 'limits': budget['budgets'],
        'scope': 'synthetic_local_http_sqlite_not_production',
        'field_inp': 'NOT_MEASURED', 'accepted_leads': accepted,
        'observed_duration_s': budget['soak']['minimum_duration_s'],
        'api_latency_samples_ms': [1.0] * accepted,
        'api_p50_ms': 1.0, 'api_p95_ms': 1.0, 'api_p99_ms': 1.0, 'api_max_ms': 1.0,
        'rss_sample_epochs_kib': [[1024] * 90, [1280] * 90],
        'child_rss_sample_epochs_kib': [[512] * 90, [0] * 90],
        'child_process_sample_epochs': [[1] * 90, [0] * 90],
        'rss_peak_kib': 1280, 'rss_growth_max_kib': 0,
        'tree_vm_rss_sum_peak_kib': 1536, 'observed_child_processes_peak': 1,
        'resource_scope': 'sampled_server_plus_descendants_sum_vm_rss_not_cgroup_peak',
        'threads_peak': 4, 'pending_outbox_peak': 2, 'backup_checkpoints': 2,
        'process_crash_and_restart': True, 'drain_elapsed_s': 1.0,
        'final_sqlite_integrity': 'ok', 'idempotent_replays': 100,
        'outbox': {'leads': accepted, 'pending': 0, 'delivered': accepted, 'failed': 0},
        'crm': {'invalid_hmac': 0, 'invalid_payloads': 0,
                'unexpected_transport_aborts': 0, 'expected_crash_aborts': 0,
                'observed_distinct_leads': accepted, 'total_webhook_attempts': accepted + 3,
                'http_status_counts': {'200': accepted, '408': 1, '429': 1, '503': 1}},
    }
    return report, budget


@pytest.mark.parametrize('verifier', [verify, verify_soak], ids=['standalone', 'meta'])
def test_complete_finite_measurements_are_accepted(evidence, verifier):
    report, budget = evidence
    assert verifier(report, budget, HEAD)


@pytest.mark.parametrize('verifier,reason', [(verify, 'latency_provenance_or_budget'),
                                           (verify_soak, 'latency_limit')],
                         ids=['standalone', 'meta'])
def test_complete_coherent_overbudget_report_is_rejected(evidence, verifier, reason):
    report, budget = evidence
    assert verifier(report, budget, HEAD)
    over = budget['budgets']['maximum_p99_lead_ms'] + 1.0
    report['api_latency_samples_ms'] = [over] * report['accepted_leads']
    for key in ('api_p50_ms', 'api_p95_ms', 'api_p99_ms', 'api_max_ms'):
        report[key] = over
    with pytest.raises(ValueError, match=reason):
        verifier(report, budget, HEAD)


@pytest.mark.parametrize('verifier', [verify, verify_soak], ids=['standalone', 'meta'])
@pytest.mark.parametrize('field,value', [
    ('observed_duration_s', float('nan')),
    ('observed_duration_s', float('inf')),
    ('api_p99_ms', float('nan')),
    ('drain_elapsed_s', float('nan')),
    ('drain_elapsed_s', -1.0),
    ('threads_peak', float('nan')),
    ('threads_peak', -1),
    ('pending_outbox_peak', float('-inf')),
    ('backup_checkpoints', float('inf')),
    ('accepted_leads', 3000.0),
    ('process_crash_and_restart', 'false'),
    ('rss_growth_max_kib', False),
    ('observed_child_processes_peak', True),
])
def test_invalid_scalar_measurements_are_rejected(evidence, verifier, field, value):
    report, budget = evidence
    report[field] = value
    with pytest.raises(ValueError):
        verifier(report, budget, HEAD)


@pytest.mark.parametrize('verifier', [verify, verify_soak], ids=['standalone', 'meta'])
@pytest.mark.parametrize('section,field,value', [
    ('outbox', 'pending', False),
    ('outbox', 'failed', 0.0),
    ('outbox', 'delivered', 3000.0),
    ('crm', 'invalid_hmac', False),
    ('crm', 'invalid_payloads', 0.0),
    ('crm', 'unexpected_transport_aborts', False),
    ('crm', 'observed_distinct_leads', 3000.0),
    ('crm', 'total_webhook_attempts', float('inf')),
])
def test_delivery_counts_are_nonnegative_integers(evidence, verifier, section, field, value):
    report, budget = evidence
    report[section][field] = value
    with pytest.raises(ValueError):
        verifier(report, budget, HEAD)


@pytest.mark.parametrize('verifier', [verify, verify_soak], ids=['standalone', 'meta'])
@pytest.mark.parametrize('value', [True, 1.5, float('inf')])
def test_fault_class_counts_are_integers(evidence, verifier, value):
    report, budget = evidence
    report['crm']['http_status_counts']['408'] = value
    with pytest.raises(ValueError):
        verifier(report, budget, HEAD)


@pytest.mark.parametrize('verifier', [verify, verify_soak], ids=['standalone', 'meta'])
def test_negative_parent_rss_cannot_cancel_measured_child_memory(evidence, verifier):
    report, budget = evidence
    report.update(rss_sample_epochs_kib=[[-1024] * 90, [-1280] * 90],
                  rss_peak_kib=-1024, rss_growth_max_kib=0,
                  tree_vm_rss_sum_peak_kib=-512)
    with pytest.raises(ValueError):
        verifier(report, budget, HEAD)


@pytest.mark.parametrize('verifier', [verify, verify_soak], ids=['standalone', 'meta'])
def test_child_memory_requires_a_measured_child(evidence, verifier):
    report, budget = evidence
    report['child_process_sample_epochs'][0][0] = 0
    with pytest.raises(ValueError):
        verifier(report, budget, HEAD)


@pytest.mark.parametrize('verifier', [verify, verify_soak], ids=['standalone', 'meta'])
def test_fault_counts_cannot_exceed_total_attempts(evidence, verifier):
    report, budget = evidence
    report['crm']['http_status_counts']['408'] = report['crm']['total_webhook_attempts'] + 1
    with pytest.raises(ValueError):
        verifier(report, budget, HEAD)


@pytest.mark.parametrize('verifier', [verify, verify_soak], ids=['standalone', 'meta'])
@pytest.mark.parametrize('corruption', ['schema', 'missing_success', 'extra_attempt',
                                      'unexplained_abort', 'unknown_status'])
def test_report_and_receiver_accounting_are_consistent(evidence, verifier, corruption):
    report, budget = evidence
    crm = report['crm']
    statuses = crm['http_status_counts']
    if corruption == 'schema':
        report['schema'] = 'unrecognized'
    elif corruption == 'missing_success':
        statuses['503'] += statuses.pop('200')
    elif corruption == 'extra_attempt':
        crm['total_webhook_attempts'] += 1
    elif corruption == 'unexplained_abort':
        statuses['400'] = 1
        statuses['503'] -= 1
    else:
        statuses['201'] = statuses.pop('200')
    with pytest.raises(ValueError):
        verifier(report, budget, HEAD)


@pytest.mark.parametrize('verifier', [verify, verify_soak], ids=['standalone', 'meta'])
def test_late_success_retries_and_bounded_crash_aborts_are_valid(evidence, verifier):
    report, budget = evidence
    crm = report['crm']
    # A response after the sender's deadline and a later retry both count as 200.
    crm['total_webhook_attempts'] += 2
    crm['http_status_counts']['200'] += 2
    crm['expected_crash_aborts'] = 4
    crm['http_status_counts']['400'] = 4
    # A zombie can still be counted while its RSS is zero.
    report['child_process_sample_epochs'][1][0] = 1
    assert verifier(report, budget, HEAD)


@pytest.mark.parametrize('duplicate', ['status', 'nested_count'])
def test_standalone_cli_rejects_duplicate_json_fields(evidence, tmp_path, duplicate):
    report, _ = evidence
    raw = json.dumps(report)
    if duplicate == 'status':
        raw = raw.replace('"status": "PASS"', '"status": "FAIL", "status": "PASS"')
    else:
        raw = raw.replace('"invalid_hmac": 0', '"invalid_hmac": 1, "invalid_hmac": 0')
    path = tmp_path / 'ambiguous-soak.json'
    path.write_text(raw)
    result = subprocess.run(
        [sys.executable, str(ROOT / 'tools/verify_soak_evidence.py'),
         '--report', str(path), '--expected-head', HEAD],
        cwd=ROOT, capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'soak-verification FAIL' in result.stderr


def test_standalone_cli_rejects_overflowing_json_number(evidence, tmp_path):
    report, _ = evidence
    raw = json.dumps(report).replace('"total_webhook_attempts": 3003',
                                     '"total_webhook_attempts": 1e309')
    assert '1e309' in raw
    path = tmp_path / 'overflowing-soak.json'
    path.write_text(raw)
    result = subprocess.run(
        [sys.executable, str(ROOT / 'tools/verify_soak_evidence.py'),
         '--report', str(path), '--expected-head', HEAD],
        cwd=ROOT, capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'soak-verification FAIL' in result.stderr
