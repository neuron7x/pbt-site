"""Негативні контролі доказу повноти сканування; синтетичні звіти."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.security_receipt import required_packages, verify_report


def report():
    return {'dependencies': [
        {'name': 'Example_Pkg', 'version': '1.0.0', 'vulns': []},
        {'name': 'other', 'version': '2.1', 'vulns': []},
    ], 'fixes': []}


REQUIREMENTS = (b'example-pkg==1.0 \\\n    --hash=sha256:' + b'a' * 64 + b'\n'
                b'other==2.1 \\\n    --hash=sha256:' + b'b' * 64 + b'\n')


def test_valid_report_normalizes_names_and_versions():
    assert verify_report(json.dumps(report()), required_packages(REQUIREMENTS)) == 2


@pytest.mark.parametrize('mutation', [
    'missing', 'extra', 'changed_version', 'duplicate', 'skip', 'vulnerability',
    'invalid_name', 'invalid_version', 'missing_vulns', 'empty', 'fixes', 'bad_schema',
])
def test_report_rejects_coverage_gaps_and_unverified_clean(mutation):
    obj = copy.deepcopy(report())
    if mutation == 'missing': obj['dependencies'].pop()
    if mutation == 'extra': obj['dependencies'].append({'name': 'extra', 'version': '1', 'vulns': []})
    if mutation == 'changed_version': obj['dependencies'][0]['version'] = '9.9'
    if mutation == 'duplicate': obj['dependencies'].append(obj['dependencies'][0])
    if mutation == 'skip': obj['dependencies'][0]['skip_reason'] = 'unavailable'
    if mutation == 'vulnerability': obj['dependencies'][0]['vulns'] = [{'id': 'TEST-1'}]
    if mutation == 'invalid_name': obj['dependencies'][0]['name'] = 'bad name'
    if mutation == 'invalid_version': obj['dependencies'][0]['version'] = 'not-a-version'
    if mutation == 'missing_vulns': del obj['dependencies'][0]['vulns']
    if mutation == 'empty': obj['dependencies'] = []
    if mutation == 'fixes': obj['fixes'] = [{}]
    if mutation == 'bad_schema': del obj['fixes']
    with pytest.raises(ValueError):
        verify_report(json.dumps(obj), required_packages(REQUIREMENTS))


@pytest.mark.parametrize('source', [
    b'', b'other>=2.1\n', b'other==2.1\n', b'other==2.1; python_version > "3"\n',
    REQUIREMENTS + b'--index-url https://invalid.example\n',
    REQUIREMENTS + b'other==2.1 \\\n  --hash=sha256:' + b'c' * 64 + b'\n',
])
def test_unsupported_or_incomplete_requirements_fail_closed(source):
    with pytest.raises((ValueError, UnicodeError)):
        required_packages(source)


def test_actual_requirements_require_packaging_which_old_report_omitted():
    expected = required_packages((ROOT / 'requirements.txt').read_bytes())
    assert 'packaging' in expected
    incomplete = {'dependencies': [{'name': k, 'version': str(v), 'vulns': []}
                                   for k, v in expected.items() if k != 'packaging'], 'fixes': []}
    with pytest.raises(ValueError, match='scanner_coverage_mismatch'):
        verify_report(json.dumps(incomplete), expected)


@pytest.mark.parametrize('payload', [
    '{"dependencies":[{"name":"example-pkg","version":"1.0",'
    '"vulns":[{"id":"CVE-2026-0001"}],"vulns":[]},'
    '{"name":"other","version":"2.1","vulns":[]}],"fixes":[]}',
    '{"dependencies":[{"name":"example-pkg","version":"1.0","vulns":[],'
    '"extra":NaN},{"name":"other","version":"2.1","vulns":[]}],"fixes":[]}',
    '{"dependencies":[],"dependencies":[{"name":"example-pkg","version":"1.0",'
    '"vulns":[]},{"name":"other","version":"2.1","vulns":[]}],"fixes":[]}',
])
def test_duplicate_json_keys_and_nonstandard_constants_fail_closed(payload):
    with pytest.raises(ValueError):
        verify_report(payload, required_packages(REQUIREMENTS))


def make_repo(tmp_path, source, lockfile='requirements.txt'):
    repo = tmp_path / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', '--template=', str(repo)], check=True)
    requirements = repo / lockfile
    requirements.write_bytes(source)
    subprocess.run(['git', 'add', lockfile], cwd=repo, check=True)
    subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                    '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null',
                    'commit', '-qm', 'synthetic requirements'], cwd=repo, check=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    return repo, requirements, head


def invoke(tmp_path, *, outcome='success', baseline='success', scan=None, source=REQUIREMENTS,
           output_b64='', after_commit=None, head_override=None, other_path=False,
           lockfile='requirements.txt'):
    repo, requirements, head = make_repo(tmp_path, source, lockfile=lockfile)
    if after_commit is not None:
        requirements.write_bytes(after_commit)
    if other_path:
        requirements = tmp_path / 'other.txt'
        requirements.write_bytes(source)
    scan_path = tmp_path / 'report.json'
    if scan is not None:
        scan_path.write_text(scan, encoding='utf-8')
    output = tmp_path / 'receipt.json'
    # Synthetic metadata exercises provenance without installing a scanner.
    dist = tmp_path / 'synthetic_metadata' / 'pip_audit-9.9.dist-info'
    dist.mkdir(parents=True, exist_ok=True)
    (dist / 'METADATA').write_text('Metadata-Version: 2.1\nName: pip-audit\nVersion: 9.9\n')
    env = {**os.environ, 'PBT_HEAD_SHA': head_override or head, 'AUDIT_OUTCOME': outcome,
           'AUDIT_BASELINE_OUTCOME': baseline,
           'PYTHONPATH': str(dist.parent),
           'AUDIT_OUTPUT_B64': output_b64, 'PYTHONDONTWRITEBYTECODE': '1'}
    result = subprocess.run([sys.executable, str(ROOT / 'tools/security_receipt.py'),
                             '--requirements', str(requirements), '--report', str(scan_path),
                             '--output', str(output)], cwd=repo, env=env, capture_output=True, text=True, timeout=10)
    return result, json.loads(output.read_text())


def test_receipt_binds_clean_report_and_requirements_bytes(tmp_path):
    text = json.dumps(report())
    result, receipt = invoke(tmp_path, scan=text)
    assert result.returncode == 0, result.stderr
    assert len(receipt['head_sha']) == 40 and receipt['dependency_count'] == 2
    assert receipt['requirements_match_head_blob'] is True
    assert receipt['requirements_sha256'] == hashlib.sha256(REQUIREMENTS).hexdigest()
    assert receipt['scanner_output_sha256'] == hashlib.sha256(text.encode()).hexdigest()
    assert receipt['scanner_output'] == text and receipt['validation_errors'] == []
    assert receipt['disable_pip'] is True and receipt['service'] == 'OSV'
    assert receipt['scanner_version'] == '9.9'


@pytest.mark.parametrize('scan', [None, '', 'not json'])
def test_missing_or_malformed_report_is_a_failure_with_receipt(tmp_path, scan):
    result, receipt = invoke(tmp_path, scan=scan)
    assert result.returncode != 0
    assert receipt['validation_errors'] and receipt['outcome'] == 'success'


def test_failed_action_preserves_failure_output_and_cannot_be_clean(tmp_path):
    failure = 'a synthetic failure with a finding'
    result, receipt = invoke(tmp_path, outcome='failure', scan=json.dumps(report()),
                             output_b64=base64.b64encode(failure.encode()).decode())
    assert result.returncode != 0
    assert receipt['action_failure_output'] == failure
    assert 'audit_step_not_successful' in receipt['validation_errors']


def test_failed_baseline_scan_cannot_be_replaced_by_clean_complete_scan(tmp_path):
    result, receipt = invoke(tmp_path, baseline='failure', scan=json.dumps(report()))
    assert result.returncode != 0
    assert receipt['baseline_outcome'] == 'failure'
    assert 'baseline_audit_not_successful' in receipt['validation_errors']


def test_corrupt_action_output_and_requirements_rejected(tmp_path):
    result, receipt = invoke(tmp_path, scan=json.dumps(report()), source=b'invalid', output_b64='***')
    assert result.returncode != 0
    assert 'invalid_action_output_encoding' in receipt['validation_errors']
    assert any(x.startswith('requirements_invalid:') for x in receipt['validation_errors'])


@pytest.mark.parametrize('mutation,error', [
    ({'after_commit': REQUIREMENTS + b'\n# changed\n'}, 'requirements_blob_mismatch'),
    ({'head_override': 'b' * 40}, 'git_head_mismatch'),
    ({'other_path': True}, 'requirements_path_mismatch'),
])
def test_git_head_requirements_provenance_is_mandatory(tmp_path, mutation, error):
    result, receipt = invoke(tmp_path, scan=json.dumps(report()), **mutation)
    assert result.returncode != 0
    assert receipt['requirements_match_head_blob'] is False
    assert error in receipt['validation_errors']


def test_sast_lockfile_has_fully_declared_packages_not_covered_by_primary_only():
    source = (ROOT / 'requirements-sast.txt').read_bytes()
    expected = required_packages(source)
    assert len(expected) == 7 and 'bandit' in expected and 'pyyaml' in expected
    missing = {'dependencies': [{'name': k, 'version': str(v), 'vulns': []}
                                for k, v in expected.items() if k != 'bandit'], 'fixes': []}
    with pytest.raises(ValueError, match='scanner_coverage_mismatch'):
        verify_report(json.dumps(missing), expected)


def test_sast_lock_receipt_accepts_only_exact_approved_git_blob(tmp_path):
    result, receipt = invoke(tmp_path, scan=json.dumps(report()),
                             lockfile='requirements-sast.txt')
    assert result.returncode == 0, result.stderr
    assert receipt['dependency_count'] == 2
    assert receipt['requirements_match_head_blob'] is True
    assert receipt['input'].endswith('requirements-sast.txt')
    assert receipt['validation_errors'] == []


def test_sast_lock_modified_after_commit_is_rejected(tmp_path):
    result, receipt = invoke(tmp_path, scan=json.dumps(report()),
                             lockfile='requirements-sast.txt',
                             after_commit=REQUIREMENTS + b'\n# changed\n')
    assert result.returncode != 0
    assert 'requirements_blob_mismatch' in receipt['validation_errors']


def test_arbitrary_lock_filename_is_rejected_even_when_git_committed(tmp_path):
    result, receipt = invoke(tmp_path, scan=json.dumps(report()), lockfile='other-lock.txt')
    assert result.returncode != 0
    assert 'requirements_path_mismatch' in receipt['validation_errors']



def test_success_without_scanner_version_is_rejected(tmp_path, monkeypatch):
    from tools import security_receipt as receipt_tool
    repo, requirements, head = make_repo(tmp_path, REQUIREMENTS)
    scan = tmp_path / 'report.json'
    scan.write_text(json.dumps(report()))
    output = tmp_path / 'receipt.json'
    monkeypatch.chdir(repo)
    monkeypatch.setenv('PBT_HEAD_SHA', head)
    monkeypatch.setenv('AUDIT_OUTCOME', 'success')
    monkeypatch.setenv('AUDIT_BASELINE_OUTCOME', 'success')
    monkeypatch.setenv('AUDIT_OUTPUT_B64', '')
    monkeypatch.setattr(sys, 'argv', ['security_receipt.py', '--requirements', str(requirements),
                                     '--report', str(scan), '--output', str(output)])

    def missing(_):
        raise receipt_tool.metadata.PackageNotFoundError('pip-audit')

    monkeypatch.setattr(receipt_tool.metadata, 'version', missing)
    assert receipt_tool.main() == 1
    result = json.loads(output.read_text())
    assert result['scanner_version'] is None
    assert 'scanner_version_unavailable_or_invalid' in result['validation_errors']
