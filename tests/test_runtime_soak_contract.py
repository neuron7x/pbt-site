"""Contract tests for a synthetic 30-minute soak — not a field-performance claim."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / 'config' / 'runtime-soak-budgets.json'


def test_soak_duration_and_budgets_cannot_be_diluted():
    cfg = json.loads(CONFIG.read_text())
    assert cfg['soak']['minimum_duration_s'] >= 1800
    assert cfg['soak']['minimum_accepted'] >= 3000
    assert cfg['budgets']['maximum_p99_lead_ms'] <= 2000
    assert cfg['budgets']['maximum_rss_kib'] <= 262144
    assert cfg['budgets']['maximum_rss_growth_kib_per_process'] <= 65536
    assert cfg['budgets']['maximum_pending_outbox'] <= 128
    assert cfg['budgets']['maximum_failed_deliveries'] == 0
    assert cfg['budgets']['minimum_backup_checkpoints'] >= 2


def test_soak_mode_refuses_tiny_duration_without_creating_evidence(tmp_path):
    report = tmp_path / 'forbidden.json'
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'tools/runtime_soak.py'),
         '--profile', 'soak', '--duration-s', '8', '--report', str(report)],
        text=True, capture_output=True, timeout=10, check=False, cwd=ROOT)
    assert proc.returncode == 2 and 'below locked test budget' in proc.stderr
    assert not report.exists()


def test_short_smoke_real_socket_fault_recovery_and_hmac(tmp_path):
    report = tmp_path / 'smoke.json'
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'tools/runtime_soak.py'),
         '--profile', 'smoke', '--duration-s', '10', '--report', str(report)],
        text=True, capture_output=True, timeout=50, check=False, cwd=ROOT)
    assert report.is_file(), proc.stdout + proc.stderr
    result = json.loads(report.read_text())
    assert proc.returncode == 0, result
    assert result['status'] == 'PASS' and result['violations'] == []
    assert result['accepted_leads'] >= 24
    assert result['process_crash_and_restart'] is True
    assert result['outbox']['delivered'] == result['accepted_leads']
    assert result['outbox']['failed'] == 0
    assert result['crm']['invalid_hmac'] == 0
    assert result['backup_checkpoints'] >= 2
    assert result['field_inp'] == 'NOT_MEASURED'
    assert '0671234567' not in report.read_text() and 'local-test-only-secret' not in report.read_text()
