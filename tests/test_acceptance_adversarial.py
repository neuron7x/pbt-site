"""§3 of the closure directive: the release evaluator itself is the unit under attack.

Each test starts from a synthetic but complete evidence set in a throwaway git repository, reaches a positive
control through the only promotion path, then falsifies one thing. Synthetic: no real CI run is claimed here.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import date

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_meta_evidence_gate import build_state, junit  # noqa: E402
from tools import assurance_check as ac, evidence_reconcile as er, external_receipts as ex, meta_evidence_gate as gate  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _git(repo, *args):
    return subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *args], cwd=repo, check=True,
                          capture_output=True, text=True, timeout=30).stdout.strip()


def _commit(repo, message):
    _git(repo, 'add', '-A')
    _git(repo, 'commit', '-qm', message)
    return _git(repo, 'rev-parse', 'HEAD')


def _cases_for(ledger, catalog, drop=()):
    refs = set()
    for _, spec in er.bindable_units(ledger):
        refs.update(spec['tests'])
    for m in catalog['mutants']:
        if m.get('oracle') and m['oracle'][0] != 'node':
            refs.update(m['oracle'])
    cases = []
    for reference in sorted(refs - set(drop)):
        path, _, function = reference.partition('::')
        cases.append((path[:-3].replace('/', '.'), function or 'test_any'))
    return cases


class World:
    """measured revision → CI-shaped ZIPs → reconcile → closure commit, like the real flow."""

    def __init__(self, tmp, drop=(), verdicts=None):
        self.repo, self.evidence = tmp / 'repo', tmp / 'evidence'
        self.repo.mkdir()
        self.evidence.mkdir()
        for name in ('config', 'assurance', 'tests'):
            shutil.copytree(ROOT / name, self.repo / name, ignore=shutil.ignore_patterns('__pycache__', 'evidence'))
        (self.repo / 'assurance/evidence').mkdir()
        _git(self.repo, 'init', '-q')
        self.base = _commit(self.repo, 'base')
        (self.repo / 'marker').write_text('source')
        ledger = json.loads((self.repo / 'assurance/ledger.json').read_text(encoding='utf-8'))
        catalog_raw = (self.repo / 'config/mutation-catalog.json').read_bytes()
        catalog = json.loads(catalog_raw)
        meta, policy, _, _ = build_state(self.evidence, 'f' * 40, self.base)  # Only to learn the budgets the fixture uses.
        (self.repo / 'config/runtime-soak-budgets.json').write_text(json.dumps(policy))
        self.head = _commit(self.repo, 'measured')
        meta, policy, _, self.contents = build_state(self.evidence, self.head, self.base,
                                                     extra_release_cases=_cases_for(ledger, catalog, drop),
                                                     extra_mutation_verdicts=verdicts, catalog_raw=catalog_raw)
        meta['target'] = {'kind': 'push', 'pr_number': None, 'ref': 'refs/heads/main'}
        del meta['artifacts']['baseline']
        for run in meta['runs'].values():
            run['event'] = 'push'
            run['jobs'].pop('Independent exact-main make gate (no main mutation)', None)
        self.meta = meta
        self._write_manifest()

    def _write_manifest(self):
        (self.evidence / 'manifest.json').write_text(json.dumps(self.meta))

    def close(self):
        er.close(self.repo, self.evidence)
        self.target = _commit(self.repo, 'closure')
        return self.target

    def accept(self, target=None):
        return ac.accept_engineering(self.repo, target or self.target, self.evidence)

    def edit_json(self, rel, fn):
        path = self.repo / rel
        data = json.loads(path.read_text(encoding='utf-8'))
        fn(data)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1))


@pytest.fixture
def world(tmp_path):
    w = World(tmp_path)
    w.close()
    return w


def test_authentic_evidence_is_accepted(world):
    """Positive control: without it, every rejection below could be an evaluator that rejects everything."""
    d = world.accept()
    assert d['technical_completion'] == 'PASS'
    assert all(d['claims'][f'C{i}'] == 'PASS' for i in range(1, 10))
    assert d['claims']['C10'] == 'UNKNOWN' and d['C0'] == 'UNKNOWN'
    assert d['dispositions'] == {'VERIFIED': 30, 'BLOCKED_EXTERNAL': 18}
    assert d['evidence_sha'] == world.head and d['target_sha'] == world.target
    receipts = json.loads((world.repo / f'assurance/evidence/{world.head}/receipts.json').read_text())
    row = receipts['units']['DB-01'][0]
    for field in ('repository', 'source_sha', 'workflow_run_id', 'run_attempt', 'job_id', 'artifact_id', 'artifact_sha256',
                  'junit_testcase_ids', 'test_outcome', 'oracle_identifier', 'negative_control_identifier'):
        assert row[field], field
    assert row['source_sha'] == world.head and row['test_outcome'] == 'passed'


def test_forged_all_pass_ledger_is_not_accepted(tmp_path):
    """Statuses edited by hand, real test names, current SHA as the only evidence."""
    w = World(tmp_path)

    def forge(ledger):
        ledger.update(stage='closed', evidence_sha=w.head)
        for item in ledger['obligations']:
            if item['disposition'] is None:
                item.update(disposition='VERIFIED', execution_status='VERIFIED', verification_status='CONFIRMED',
                            verified_at_sha=w.head, artifact_paths=['tests/test_api.py'])

    def forge_case(case):
        case['evidence_sha'] = w.head
        for claim in case['claims'].values():
            for leaf in claim['leaves']:
                leaf.update(status='PASS', evidence=[{'sha': w.head}])
    w.edit_json('assurance/ledger.json', forge)
    w.edit_json('assurance/case.json', forge_case)
    forged = _commit(w.repo, 'forged closure')
    ac.schema_check(w.repo)  # It is well formed. That is exactly why schema validity must not mean acceptance.
    with pytest.raises(ac.Rejected, match='no_execution_evidence_supplied'):
        ac.accept_engineering(w.repo, forged, None)
    with pytest.raises(FileNotFoundError):  # Real ZIPs, but no receipts were ever bound.
        ac.accept_engineering(w.repo, forged, w.evidence)


def test_test_that_exists_but_never_ran_is_rejected(tmp_path):
    reference = 'tests/test_data_integrity.py::test_outbox_insert_inside_real_acceptance_path_keeps_fk_clean'
    assert ac._test_exists(ROOT, reference)
    w = World(tmp_path, drop=[reference])
    with pytest.raises(er.Unbound, match='test_never_executed'):
        er.close(w.repo, w.evidence)


def test_skipped_critical_test_is_rejected(tmp_path):
    w = World(tmp_path)
    w2 = w.contents['release']['artifacts/full-junit.xml'].decode()
    w.contents['release']['artifacts/full-junit.xml'] = w2.replace(
        'name="test_process_death_at_each_acceptance_cutpoint[0]" />',
        'name="test_process_death_at_each_acceptance_cutpoint[0]"><skipped/></testcase>').encode()
    _rewrite(w, 'release')
    with pytest.raises(gate.Rejected, match='junit'):
        er.close(w.repo, w.evidence)


def _rewrite(w, role):
    from test_meta_evidence_gate import pack, sha
    path = w.evidence / f'{role}.zip'
    path.write_bytes(pack(w.contents[role]))
    w.meta['artifacts'][role]['sha256'] = sha(path.read_bytes())
    w._write_manifest()


def test_wrong_source_evidence_is_rejected(world):
    world.meta['head_sha'] = 'c' * 40
    world._write_manifest()
    with pytest.raises(ac.Rejected, match='evidence_for_other_revision'):
        world.accept()


def test_pull_request_evidence_cannot_certify_main(world):
    world.meta['target'] = {'kind': 'pull_request', 'pr_number': 1, 'ref': 'refs/pull/1/head'}
    world._write_manifest()
    with pytest.raises(ac.Rejected, match='evidence_not_from_main'):
        world.accept()


def test_hand_edited_receipts_are_rejected(world):
    rel = f'assurance/evidence/{world.head}/receipts.json'
    world.edit_json(rel, lambda r: r['units']['DB-01'][0].update(workflow_run_id=999999))
    target = _commit(world.repo, 'edit receipts')
    with pytest.raises(ac.Rejected, match='committed_receipts_differ'):
        world.accept(target)


def test_changed_normative_specification_is_rejected(world):
    world.edit_json('assurance/source/tasks.json', lambda tasks: tasks[0].update(acceptance='anything goes'))
    target = _commit(world.repo, 'weaken the contract')
    with pytest.raises(ac.Rejected, match='normative_specification_changed'):
        world.accept(target)


def test_oracle_or_config_changed_after_measurement_voids_the_proof(world):
    (world.repo / 'tests/test_api.py').write_text('def test_nothing():\n    pass\n')
    with pytest.raises(ac.Rejected, match='proof_void_changed_tests/test_api.py'):
        world.accept(_commit(world.repo, 'gut an oracle'))


def test_threat_model_and_budgets_are_not_reports(world):
    world.edit_json('config/evidence-policy.json', lambda p: p['mobile'].update(lcp_ms=99999))
    with pytest.raises(ac.Rejected, match='proof_void_changed_config/evidence-policy.json'):
        world.accept(_commit(world.repo, 'relax the budget'))


def test_ledger_contract_changed_after_measurement_is_rejected(world):
    world.edit_json('assurance/ledger.json', lambda l: l['obligations'][8].update(tests=l['obligations'][8]['tests'][:1], mutants=[]))
    with pytest.raises((ac.Rejected,)):
        world.accept(_commit(world.repo, 'shrink the oracle set'))


def test_case_structure_changed_after_measurement_is_rejected(world):
    world.edit_json('assurance/case.json', lambda c: c['claims']['C1']['leaves'].pop())
    with pytest.raises(ac.Rejected, match='case_structure_changed'):
        world.accept(_commit(world.repo, 'drop a leaf'))


def test_required_workflow_that_never_completed_is_rejected(tmp_path):
    w = World(tmp_path)
    name = next(iter(w.meta['runs']['soak']['jobs']))
    w.meta['runs']['soak']['jobs'][name].update(status='in_progress', conclusion=None)
    w._write_manifest()
    with pytest.raises(gate.Rejected, match='required_job_not_successful'):
        er.close(w.repo, w.evidence)


def test_survivor_in_the_mutation_ledger_is_rejected_whatever_the_ledger_says(tmp_path):
    w = World(tmp_path, verdicts={'M-DB-01-fk-pragma': 'SURVIVED'})
    with pytest.raises(gate.Rejected, match='mutant_not_killed_M-DB-01-fk-pragma'):
        er.close(w.repo, w.evidence)


def test_status_field_claiming_external_pass_is_rejected(world):
    def lie(case):
        for leaf in case['claims']['C10']['leaves']:
            leaf['status'] = 'PASS'
    world.edit_json('assurance/case.json', lie)
    with pytest.raises(ac.Rejected, match='claims_pass_without_derivation'):
        world.accept(_commit(world.repo, 'claim externals'))


def test_production_stays_on_hold_without_signed_receipts(world):
    d = world.accept()
    assert d['C0'] == 'UNKNOWN' and d['claims']['C10'] == 'UNKNOWN'
    assert all(v.startswith('UNKNOWN') for v in d['external'].values())
    assert set(d['external']) >= {'B1', 'B3', 'B4', 'R1', 'R2', 'R3', 'H1', 'F1', 'S1', 'D1'}


# ─── external receipts: authenticity, not presence ───────
POLICY = json.loads((ROOT / 'config/external-evidence-policy.json').read_text(encoding='utf-8'))


def _key(tmp, name):
    path = tmp / name
    subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', name, '-f', str(path)], check=True, timeout=20)
    return path


def _sign(key, file):
    subprocess.run(['ssh-keygen', '-q', '-Y', 'sign', '-f', str(key), '-n', POLICY['namespace'], str(file)], check=True, timeout=20, capture_output=True)


def _receipt(tmp, class_id, **fields):
    path = tmp / f'{class_id}.json'
    path.write_text(json.dumps({'schema': 'pbt-external-receipt-v1', 'class': class_id, **fields}))
    return path


D1 = dict(subject='site', release_sha='a' * 40, expires_on='2999-01-01')


def _signers(tmp, key):
    signers = tmp / 'allowed'
    signers.write_text(f"{POLICY['signer_identity']} {Path(str(key) + '.pub').read_text()}")
    return signers


def test_fabricated_external_receipt_never_closes_a_class(tmp_path):
    owner, stranger = _key(tmp_path, 'owner'), _key(tmp_path, 'stranger')
    signers = _signers(tmp_path, owner)
    path = _receipt(tmp_path, 'D1', **D1)
    with pytest.raises(ex.ReceiptRejected, match='unsigned'):
        ex.validate(path, 'D1', POLICY, signers, 'a' * 40)
    _sign(stranger, path)
    with pytest.raises(ex.ReceiptRejected, match='bad_signature'):
        ex.validate(path, 'D1', POLICY, signers, 'a' * 40)
    with pytest.raises(ex.ReceiptRejected, match='no_authorized_signer'):
        ex.validate(path, 'D1', POLICY, ROOT / 'config/owner-allowed-signers', 'a' * 40)


def test_committed_signer_list_is_empty_so_nothing_can_close_today():
    assert (ROOT / 'config/owner-allowed-signers').read_text().strip() == ''


def test_signed_receipt_positive_control_then_each_defect(tmp_path):
    owner = _key(tmp_path, 'owner')
    signers = _signers(tmp_path, owner)
    path = _receipt(tmp_path, 'D1', **D1)
    _sign(owner, path)
    assert ex.validate(path, 'D1', POLICY, signers, 'a' * 40)['release_sha'] == 'a' * 40
    with pytest.raises(ex.ReceiptRejected, match='other_revision'):
        ex.validate(path, 'D1', POLICY, signers, 'b' * 40)
    with pytest.raises(ex.ReceiptRejected, match='expired'):
        ex.validate(path, 'D1', POLICY, signers, 'a' * 40, today=date(3000, 1, 1))
    path.write_text(path.read_text().replace('site', 'other'))  # Any edit after signing.
    with pytest.raises(ex.ReceiptRejected, match='bad_signature'):
        ex.validate(path, 'D1', POLICY, signers, 'a' * 40)


@pytest.mark.parametrize('class_id,fields,reason', [
    ('B1', {'subject': 'prices'}, 'missing_effective_from'),
    ('D1', {'subject': 'x', 'release_sha': 'a' * 40}, 'expiry_required'),
    ('B1', {'subject': 'x', 'effective_from': '2026-01-01', 'document_sha256': 'y', 'revoked': True}, 'revoked'),
])
def test_signed_but_incomplete_receipt_is_rejected(tmp_path, class_id, fields, reason):
    owner = _key(tmp_path, 'owner')
    path = _receipt(tmp_path, class_id, **fields)
    _sign(owner, path)
    with pytest.raises(ex.ReceiptRejected, match=reason):
        ex.validate(path, class_id, POLICY, _signers(tmp_path, owner), 'a' * 40)


def test_receipt_for_another_class_is_rejected(tmp_path):
    owner = _key(tmp_path, 'owner')
    path = tmp_path / 'B1.json'
    path.write_text(json.dumps({'schema': 'pbt-external-receipt-v1', 'class': 'D1', **D1}))
    _sign(owner, path)
    with pytest.raises(ex.ReceiptRejected, match='wrong_class'):
        ex.validate(path, 'B1', POLICY, _signers(tmp_path, owner), 'a' * 40)
