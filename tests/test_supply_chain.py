"""ADV-06/EVD-01/NET-07: provenance receipts and scanner gate reject what they must."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import sast_gate, supply_chain as sc

ROOT = Path(__file__).resolve().parents[1]
GOOD_SHA = 'a' * 40
LOCK = 'pkg==1.0 \\\n    --hash=sha256:' + 'a' * 64 + '\n'


@pytest.fixture
def repo(tmp_path):
    (tmp_path / '.github/workflows').mkdir(parents=True)
    (tmp_path / '.github/workflows/ci.yml').write_text(f'jobs:\n  a:\n    steps:\n      - uses: actions/checkout@{GOOD_SHA}\n')
    for name in sc.LOCKS:
        (tmp_path / name).write_text(LOCK)
    run = lambda *a: subprocess.run(['git', *a], cwd=tmp_path, check=True, capture_output=True)
    run('init', '-q')
    run('add', '-A')
    run('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'x')
    return tmp_path


def _head(repo):
    return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo, capture_output=True, text=True).stdout.strip()


def test_real_repository_passes_and_sbom_lists_every_locked_requirement():
    assert sc.action_pins(ROOT)
    bom = sc.sbom(ROOT)
    names = {c['name'] for c in bom['components']}
    assert {'pytest', 'playwright', 'bandit'} <= names
    assert all(c['hashes'] for c in bom['components'])


def test_sbom_uses_cyclonedx_15_scope_and_source_lock_properties(repo):
    bom = sc.sbom(repo)
    components = bom['components']
    assert bom['bomFormat'] == 'CycloneDX' and bom['specVersion'] == '1.5'
    assert len(components) == len(sc.LOCKS)
    assert {c['scope'] for c in components} == {'required'}
    assert {c['properties'][0]['value'] for c in components} == set(sc.LOCKS)
    assert all(c['properties'][0]['name'] == 'pbt:source-lockfile' for c in components)
    assert len({c['bom-ref'] for c in components}) == len(components)
    assert sc.validate_sbom_contract(bom) == len(components)


def test_invalid_lockfile_as_scope_is_rejected(repo):
    bom = sc.sbom(repo)
    bom['components'][0]['scope'] = 'requirements.txt'
    with pytest.raises(sc.Rejected, match='invalid_component_scope'):
        sc.validate_sbom_contract(bom)


def test_missing_lock_origin_is_rejected(repo):
    bom = sc.sbom(repo)
    bom['components'][0]['properties'] = []
    with pytest.raises(sc.Rejected, match='invalid_component_lock_origin'):
        sc.validate_sbom_contract(bom)


def test_repeated_bom_ref_is_rejected(repo):
    bom = sc.sbom(repo)
    bom['components'][1]['bom-ref'] = bom['components'][0]['bom-ref']
    with pytest.raises(sc.Rejected, match='duplicate_or_missing_sbom_ref'):
        sc.validate_sbom_contract(bom)


def test_invalid_property_value_type_is_rejected(repo):
    bom = sc.sbom(repo)
    bom['components'][0]['properties'] = ['not_a_property']
    with pytest.raises(sc.Rejected, match='invalid_component_lock_origin'):
        sc.validate_sbom_contract(bom)


def test_invalid_hash_item_type_is_rejected(repo):
    bom = sc.sbom(repo)
    bom['components'][0]['hashes'] = [None]
    with pytest.raises(sc.Rejected, match='invalid_component_hashes'):
        sc.validate_sbom_contract(bom)


def test_capture_then_verify_round_trip(repo):
    receipt = sc.capture(repo, _head(repo), env={})
    assert sc.verify(repo, receipt, _head(repo))['status'] == 'PASS'
    assert receipt['slsa_level'] == 'none_claimed' and receipt['signed'] is False


def test_checkout_drift_holds_before_anything_runs(repo):
    with pytest.raises(sc.Rejected, match='checkout_differs'):
        sc.capture(repo, 'c' * 40, env={})
    with pytest.raises(sc.Rejected, match='pbt_head_sha_differs'):
        sc.capture(repo, _head(repo), env={'PBT_HEAD_SHA': 'c' * 40})


def test_github_sha_is_recorded_separately_and_cannot_stand_in_for_the_checkout(repo):
    receipt = sc.capture(repo, _head(repo), env={'GITHUB_SHA': 'd' * 40})
    assert receipt['event_sha'] == 'd' * 40 and receipt['head_sha'] == _head(repo)


def test_unpinned_action_is_rejected(repo):
    (repo / '.github/workflows/ci.yml').write_text('steps:\n  - uses: actions/checkout@v4\n')
    with pytest.raises(sc.Rejected, match='unpinned_action'):
        sc.action_pins(repo)


@pytest.mark.parametrize('text,reason', [
    ('pkg==1.0\n', 'requirement_without_hash'), ('', 'empty_lock'),
    (LOCK + 'other>=2.0 \\\n    --hash=sha256:' + 'b' * 64 + '\n', 'unpinned_requirement'),
])
def test_weak_lock_files_are_rejected(repo, text, reason):
    (repo / 'requirements.txt').write_text(text)
    with pytest.raises(sc.Rejected, match=reason):
        sc.derive(repo)


def test_stale_receipt_after_pin_or_lock_change_is_rejected(repo):
    receipt = sc.capture(repo, _head(repo), env={})
    head = _head(repo)
    (repo / 'requirements.txt').write_text(LOCK.replace('a' * 64, 'b' * 64))
    with pytest.raises(sc.Rejected, match='receipt_drift_locks'):
        sc.verify(repo, receipt, head)
    (repo / 'requirements.txt').write_text(LOCK)
    (repo / '.github/workflows/ci.yml').write_text(f'steps:\n  - uses: actions/checkout@{"e" * 40}\n')
    with pytest.raises(sc.Rejected, match='receipt_drift_action_pins'):
        sc.verify(repo, receipt, head)
    with pytest.raises(sc.Rejected, match='stale_source_revision'):
        sc.verify(repo, receipt, 'c' * 40)


# ─── broad scanner gate ──────────────────────────────────
def _report(results=(), files=30, loc=1000, errors=()):
    metrics = {f'f{i}.py': {} for i in range(files)}
    metrics['_totals'] = {'loc': loc}
    return json.dumps({'results': list(results), 'metrics': metrics, 'errors': list(errors)})


FINDING = {'test_id': 'B999', 'filename': 'server/app.py', 'code': 'x = 1', 'line_number': 1, 'issue_severity': 'HIGH'}


def test_scanner_clean_positive_control():
    assert sast_gate.evaluate(_report(), 0, [], 20)['status'] == 'PASS'


@pytest.mark.parametrize('stdout,rc,reason', [
    ('', 2, 'scanner_exit_2'), ('Traceback', 0, 'scanner_output_unparsable'), ('', 0, 'scanner_output_unparsable'),
    (_report(files=1), 0, 'scanner_scanned_too_little'), (_report(loc=0), 0, 'scanner_scanned_too_little'),
    (_report(errors=[{'filename': 'a'}]), 0, 'scanner_reported_errors'),
])
def test_scanner_that_did_not_scan_cannot_pass(stdout, rc, reason):
    result = sast_gate.evaluate(stdout, rc, [], 20)
    assert result['status'] == 'FAIL' and result['reason'] == reason


def test_open_finding_fails_and_waiver_needs_rationale_and_cannot_go_stale():
    assert sast_gate.evaluate(_report([FINDING]), 1, [], 20)['status'] == 'FAIL'
    key = sast_gate.fingerprint(FINDING)
    assert sast_gate.evaluate(_report([FINDING]), 1, [{'fingerprint': key, 'rationale': 'why'}], 20)['status'] == 'PASS'
    assert sast_gate.evaluate(_report([FINDING]), 1, [{'fingerprint': key, 'rationale': ' '}], 20)['reason'] == 'waiver_without_rationale'
    assert sast_gate.evaluate(_report(), 0, [{'fingerprint': key, 'rationale': 'why'}], 20)['status'] == 'FAIL'


def test_bidi_controls_are_still_stripped_and_absent_from_source():
    source = (ROOT / 'server/app.py').read_text(encoding='utf-8')
    assert not any(c in source for c in map(chr, [*range(0x202a, 0x202f), *range(0x2066, 0x206a)]))
    r = subprocess.run([sys.executable, '-c', f'''
import importlib.util,sys
s=importlib.util.spec_from_file_location('app',{str(ROOT / "server/app.py")!r})
a=importlib.util.module_from_spec(s);sys.modules['app']=a;s.loader.exec_module(a)
chars=[*range(0,9),11,12,*range(14,32),127,*range(0x200b,0x2010),*range(0x202a,0x202f),*range(0x2066,0x206a)]
print(a.clean("a"+"".join(map(chr,chars))+"b",5000))
'''], capture_output=True, text=True, timeout=30, env={'LEAD_DB': '/tmp/pbt-bidi-probe.db', 'DELIVERY_WORKER': '0', 'PATH': '/usr/bin'})
    assert r.stdout.strip() == 'ab', r.stdout + r.stderr
