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
    assert result['crm']['invalid_payloads'] == 0
    assert result['crm']['unexpected_transport_aborts'] == 0
    assert 0 <= result['crm']['expected_crash_aborts'] <= 4
    assert result['backup_checkpoints'] >= 2
    assert result['field_inp'] == 'NOT_MEASURED'
    import subprocess as _subprocess
    verified = _subprocess.run([
        sys.executable, str(ROOT / 'tools/verify_soak_evidence.py'), '--report', str(report),
        '--expected-head', result['source_sha']
    ], cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert verified.returncode == 0, verified.stdout + verified.stderr
    assert '0671234567' not in report.read_text() and 'local-test-only-secret' not in report.read_text()


def test_crm_rejects_complete_invalid_hmac_and_signed_invalid_payload():
    """A fully received wrong HMAC must remain a hard failure."""
    import hashlib
    import hmac
    import urllib.error
    import urllib.request
    from tools.runtime_soak import SECRET, SyntheticCRM

    crm = SyntheticCRM()
    try:
        bad = urllib.request.Request(crm.url, b'{"id":1}',
                                     {'X-PBT-Signature': '0' * 64}, method='POST')
        try:
            urllib.request.urlopen(bad, timeout=3)
            assert False, 'wrong HMAC accepted'
        except urllib.error.HTTPError as exc:
            assert exc.code == 403
        malformed = b'{"id":true}'
        signed = hmac.new(SECRET, malformed, hashlib.sha256).hexdigest()
        bad_id = urllib.request.Request(crm.url, malformed,
                                        {'X-PBT-Signature': signed}, method='POST')
        try:
            urllib.request.urlopen(bad_id, timeout=3)
            assert False, 'invalid signed payload accepted'
        except urllib.error.HTTPError as exc:
            assert exc.code == 422
        result = crm.snapshot()
        assert result['invalid_hmac'] == 1 and result['invalid_payloads'] == 1
        assert result['observed_distinct_leads'] == 0
        assert result['expected_crash_aborts'] == 0
        assert result['unexpected_transport_aborts'] == 0
    finally:
        crm.stop()


def test_crm_incomplete_transport_fails_closed_and_is_separate_from_hmac():
    """Truncation outside kill is a failure; during kill it is measured and bounded."""
    import socket
    from tools.runtime_soak import SyntheticCRM

    crm = SyntheticCRM()

    def send_partial():
        with socket.create_connection(crm.server.server_address, timeout=3) as sock:
            sock.settimeout(3)
            sock.sendall(
                b'POST /hook HTTP/1.1\r\nHost: 127.0.0.1\r\n'
                b'Content-Length: 200\r\nX-PBT-Signature: '
                + b'0' * 64 + b'\r\nConnection: close\r\n\r\n{"id":1}'
            )
            sock.shutdown(socket.SHUT_WR)
            assert b' 400 ' in sock.recv(1024)

    try:
        send_partial()
        with crm.lock:
            crm.crash_window = True
        try:
            send_partial()
        finally:
            with crm.lock:
                crm.crash_window = False
        result = crm.snapshot()
        assert result['unexpected_transport_aborts'] == 1
        assert result['expected_crash_aborts'] == 1
        assert result['invalid_hmac'] == 0
        assert result['invalid_payloads'] == 0
        assert result['observed_distinct_leads'] == 0
    finally:
        crm.stop()
