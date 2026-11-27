"""Ledger structure and the three-valued decision logic. Acceptance itself: test_acceptance_adversarial.py."""
import copy
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import assurance_check as ac

ROOT = Path(__file__).resolve().parents[1]
LEDGER = json.loads((ROOT / 'assurance/ledger.json').read_text(encoding='utf-8'))
TASKS = json.loads((ROOT / 'assurance/source/tasks.json').read_text(encoding='utf-8'))
CATALOG = {m['id'] for m in json.loads((ROOT / 'config/mutation-catalog.json').read_text(encoding='utf-8'))['mutants']}
CLASSES = set(json.loads((ROOT / 'config/external-evidence-policy.json').read_text(encoding='utf-8'))['classes'])


def _check(ledger):
    return ac.check_ledger(ledger, TASKS, ROOT, CATALOG, CLASSES)


def test_committed_ledger_is_complete_and_valid():
    assert len(_check(LEDGER)) == 48


def test_specification_graph_is_well_formed_and_pinned():
    ac.check_spec(TASKS)
    ac.check_normative(ROOT)
    bad = copy.deepcopy(TASKS)
    bad[0]['dependencies'] = ['NOPE']
    with pytest.raises(ac.Rejected, match='spec_missing_dependency'):
        ac.check_spec(bad)
    cyclic = copy.deepcopy(TASKS)
    cyclic[0]['dependencies'] = [cyclic[1]['id']]
    cyclic[1]['dependencies'] = [cyclic[0]['id']]
    with pytest.raises(ac.Rejected, match='spec_dependency_cycle'):
        ac.check_spec(cyclic)
    with pytest.raises(ac.Rejected, match='spec_duplicate_task'):
        ac.check_spec(TASKS + [TASKS[0]])


def test_decision_logic_is_conjunctive_and_three_valued():
    assert ac.decide_claim(['PASS', 'PASS']) == 'PASS'
    assert ac.decide_claim(['PASS', 'UNKNOWN']) == 'UNKNOWN'
    assert ac.decide_claim(['PASS', 'UNKNOWN', 'FAIL']) == 'FAIL'
    assert ac.decide_claim([]) == 'UNKNOWN'
    assert ac.decide_claim(['PASS', 'MAYBE']) == 'UNKNOWN'
    assert ac.decide_claim(['PASS'] * 99 + ['UNKNOWN']) == 'UNKNOWN'


def _mutated(fn):
    ledger = copy.deepcopy(LEDGER)
    fn(ledger, {o['obligation_id']: o for o in ledger['obligations']})
    return ledger


OK_VERIFIED = dict(disposition='VERIFIED', verification_status='CONFIRMED', execution_status='VERIFIED',
                   verified_at_sha='a' * 40, artifact_paths=['x'])


@pytest.mark.parametrize('mutation,reason', [
    (lambda l, e: l['obligations'].pop(), 'obligation_set_differs'),
    (lambda l, e: l['obligations'].append(copy.deepcopy(l['obligations'][0])), 'duplicate_obligation'),
    (lambda l, e: e['DB-01'].pop('counterexample'), 'missing_counterexample'),
    (lambda l, e: e['DB-01'].update(execution_status='DONE'), 'execution_status'),
    (lambda l, e: e['DB-01'].update(verification_status='PASS'), 'verification_status'),
    (lambda l, e: e['DB-01'].update(disposition='GREEN'), '_disposition'),
    (lambda l, e: e['DB-01'].update(tests=['tests/test_data_integrity.py::test_does_not_exist']), 'names_absent_test'),
    (lambda l, e: e['DB-01'].update(tests=['README.md']), 'names_absent_test'),
    (lambda l, e: e['DB-01'].update(mutants=['M-NOPE']), 'names_absent_mutant'),
    (lambda l, e: e['DB-01'].update(**OK_VERIFIED, tests=[]) if False else e['DB-01'].update({**OK_VERIFIED, 'tests': []}), 'verified_without_tests'),
    (lambda l, e: e['DB-01'].update({**OK_VERIFIED, 'verification_status': 'INFERRED'}), 'verified_but_not_confirmed'),
    (lambda l, e: e['DB-01'].update({**OK_VERIFIED, 'artifact_paths': []}), 'verified_without_execution_reference'),
    (lambda l, e: e['OPS-06'].update({**OK_VERIFIED, 'tests': ['tests/test_business_parity.py'], 'external_receipt': None}), 'verified_without_external_receipt'),
    (lambda l, e: e['OPS-06'].update(blocker=''), 'blocked_without_named_blocker'),
    (lambda l, e: e['OPS-06'].update(execution_status='IMPLEMENTED'), 'blocked_transition'),
    (lambda l, e: e['NET-08'].pop('reclassification_reason'), 'reclassified_without_split'),
    (lambda l, e: e['WEB-01'].update(subclaims=[s for s in e['WEB-01']['subclaims'] if s['kind'] == 'external']), 'reclassified_without_split'),
    (lambda l, e: e['NET-08']['subclaims'][0].update(mutants=[]), 'technical_needs_tests_and_mutants'),
    (lambda l, e: e['NET-08']['subclaims'][1].update(classes=['Z9']), 'external_class'),
    (lambda l, e: e['DB-01'].update(disposition='INAPPLICABLE_WITH_PROOF', proof=''), 'disposition_without_proof'),
    (lambda l, e: (l.update(stage='closed'), e['DB-01'].update(disposition=None)), 'needs_final_disposition'),
    (lambda l, e: e['DB-01'].update(acceptance_predicate='anything'), 'contract_differs_from_specification'),
    (lambda l, e: e['DB-01'].update(formal_invariant='weaker'), 'contract_differs_from_specification'),
    (lambda l, e: e['DB-01'].update(dependency_ids=[]), 'contract_differs_from_specification'),
])
def test_unsafe_ledger_is_rejected(mutation, reason):
    with pytest.raises(ac.Rejected, match=reason):
        _check(_mutated(mutation))


def test_verified_over_a_blocked_dependency_without_technical_part_is_rejected():
    def mutate(l, e):
        e['DB-01'].update(OK_VERIFIED)
        e['DB-01']['dependency_ids'] = ['WEB-03']
    tasks = copy.deepcopy(TASKS)
    next(t for t in tasks if t['id'] == 'DB-01')['dependencies'] = ['WEB-03']
    with pytest.raises(ac.Rejected, match='verified_over_unverified_dependency'):
        ac.check_ledger(_mutated(mutate), tasks, ROOT, CATALOG, CLASSES)


def test_every_blocked_obligation_names_its_authority_and_every_internal_has_a_negative_control():
    for item in LEDGER['obligations']:
        if item['disposition'] == 'BLOCKED_EXTERNAL':
            assert any(s['kind'] == 'external' and s['classes'] for s in item['subclaims']), item['obligation_id']
        else:
            assert item['mutants'] and item['tests'], item['obligation_id']


def test_threat_model_covers_every_endpoint_and_links_real_tests():
    model = json.loads((ROOT / 'assurance/threat-model.json').read_text(encoding='utf-8'))
    source = (ROOT / 'server/app.py').read_text(encoding='utf-8')
    endpoints = set(re.findall(r"self\.path\.split\('\?'\)\[0\] (?:==|!=) '(/[a-z/]+)'", source))
    assert endpoints == {'/api/config', '/api/health', '/api/lead', '/api/support'}, 'new endpoint: extend the threat model'
    assert endpoints <= set(model['entry_points'])
    assert len(model['threats']) >= 8
    for threat in model['threats']:
        assert threat['risk_owner'] and threat['precondition'] and threat['cwe'].startswith('CWE-')
        assert threat['tests'] or threat['status'] == 'OPEN_EXTERNAL', threat['id']
        for reference in threat['tests']:
            assert ac._test_exists(ROOT, reference), reference


def test_controls_map_names_real_tests_and_claims_no_whole_standard():
    controls = json.loads((ROOT / 'assurance/controls.json').read_text(encoding='utf-8'))
    assert controls['conformity_claim'] == 'none'
    for row in controls['controls']:
        assert row['requirement'] and row['control'] and row['code'] and row['counterexample']
        assert ac._test_exists(ROOT, row['test']), row['test']


def test_schema_mode_exits_zero_and_says_it_accepts_nothing():
    r = subprocess.run([sys.executable, str(ROOT / 'tools/assurance_check.py')], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(r.stdout)['decision'] == 'SCHEMA_VALID'


def test_acceptance_without_evidence_exits_nonzero():
    r = subprocess.run([sys.executable, str(ROOT / 'tools/assurance_check.py'), '--require', 'engineering'], capture_output=True, text=True, timeout=30)
    assert r.returncode == 1 and json.loads(r.stdout)['decision'] == 'EVIDENCE_REJECTED'
