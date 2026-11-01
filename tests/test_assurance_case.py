"""EVD-08/ADV-08: the release decision is a dependency closure; each unsafe substitution is rejected."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import assurance_check as ac

ROOT = Path(__file__).resolve().parents[1]
LEDGER = json.loads((ROOT / 'assurance/ledger.json').read_text(encoding='utf-8'))
TASKS = json.loads((ROOT / 'assurance/source/tasks.json').read_text(encoding='utf-8'))
CASE = json.loads((ROOT / 'assurance/case.json').read_text(encoding='utf-8'))
CATALOG = {m['id'] for m in json.loads((ROOT / 'config/mutation-catalog.json').read_text(encoding='utf-8'))['mutants']}
HEAD = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip() or '0' * 40


def _entries():
    return ac.check_ledger(LEDGER, TASKS, ROOT, CATALOG)


def test_committed_ledger_is_complete_and_valid():
    entries = _entries()
    assert len(entries) == 48


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


@pytest.mark.parametrize('mutation,reason', [
    (lambda l, e: l['obligations'].pop(), 'obligation_set_differs'),
    (lambda l, e: l['obligations'].append(copy.deepcopy(l['obligations'][0])), 'duplicate_obligation'),
    (lambda l, e: e['DB-01'].pop('counterexample'), 'missing_counterexample'),
    (lambda l, e: e['DB-01'].update(execution_status='DONE'), 'execution_status'),
    (lambda l, e: e['DB-01'].update(verification_status='PASS'), 'verification_status'),
    (lambda l, e: e['DB-01'].update(disposition='GREEN'), '_disposition'),
    (lambda l, e: e['DB-01'].update(tests=['tests/test_data_integrity.py::test_does_not_exist']), 'names_absent_test'),
    (lambda l, e: e['DB-01'].update(mutants=['M-NOPE']), 'names_absent_mutant'),
    (lambda l, e: e['DB-01'].update(disposition='VERIFIED', tests=[], verification_status='CONFIRMED'), 'verified_without_tests'),
    (lambda l, e: e['DB-01'].update(disposition='VERIFIED', verification_status='INFERRED'), 'verified_but_not_confirmed'),
    (lambda l, e: e['OPS-06'].update(disposition='VERIFIED', verification_status='CONFIRMED', tests=['tests/test_business_parity.py'], external_receipt=None), 'verified_without_external_receipt'),
    (lambda l, e: e['OPS-06'].update(disposition='VERIFIED', verification_status='CONFIRMED', tests=['tests/test_business_parity.py'], external_receipt='no-such-file'), 'verified_without_external_receipt'),
    (lambda l, e: e['OPS-06'].update(disposition='VERIFIED', verification_status='CONFIRMED', tests=['tests/test_business_parity.py'], external_receipt='README.md'), 'verified_without_external_receipt'),
    (lambda l, e: e['DB-01'].update(tests=['README.md']), 'names_absent_test'),
    (lambda l, e: e['OPS-06'].update(disposition='BLOCKED_EXTERNAL', blocker=''), 'blocked_without_named_blocker'),
    (lambda l, e: e['DB-01'].update(disposition='INAPPLICABLE_WITH_PROOF', proof=''), 'disposition_without_proof'),
    (lambda l, e: (l.update(stage='closed'), e['DB-01'].update(disposition=None)), 'needs_final_disposition'),
])
def test_unsafe_ledger_is_rejected(mutation, reason):
    with pytest.raises(ac.Rejected, match=reason):
        ac.check_ledger(_mutated(mutation), TASKS, ROOT, CATALOG)


def _case():
    return copy.deepcopy(CASE)


def _leaf(case, leaf_id):
    for claim in case['claims'].values():
        for leaf in claim['leaves']:
            if leaf['id'] == leaf_id:
                return leaf
    raise KeyError(leaf_id)


def test_external_claim_stays_unknown_and_release_stays_on_hold():
    verdict = ac.evaluate_case(CASE, ROOT, HEAD, _entries(), LEDGER['stage'])
    assert verdict['claims']['C10'] == 'UNKNOWN'
    assert verdict['production_release'] == 'PRODUCTION HOLD' and verdict['C0'] != 'PASS'


def test_green_ci_cannot_substitute_for_a_field_or_owner_fact():
    case = _case()
    leaf = _leaf(case, 'C10.field_inp')
    leaf['status'] = 'PASS'
    with pytest.raises(ac.Rejected, match='pass_without_evidence'):
        ac.evaluate_case(case, ROOT, HEAD, _entries())
    leaf['evidence'] = [{'sha': HEAD}]
    leaf['obligations'] = ['WEB-03']
    with pytest.raises(ac.Rejected, match='obligation_WEB-03_not_verified'):
        ac.evaluate_case(case, ROOT, HEAD, _entries())


def test_historical_sha_with_executable_drift_cannot_prove_the_target():
    case = _case()
    leaf = _leaf(case, 'C10.field_inp')
    leaf.update(status='PASS', evidence=[{'sha': '1' * 40}], obligations=['WEB-03'])
    with pytest.raises(ac.Rejected, match='stale_evidence_sha'):
        ac.evaluate_case(case, ROOT, HEAD, _entries())


@pytest.mark.parametrize('sha', ['HEAD', 'nonexistent', 'main', 'a' * 39])
def test_evidence_must_name_a_real_full_commit_not_a_matching_string(sha):
    case = _case()
    _leaf(case, 'C10.field_inp').update(status='PASS', evidence=[{'sha': sha}], obligations=['WEB-03'])
    with pytest.raises(ac.Rejected, match='stale_evidence_sha'):
        ac.evaluate_case(case, ROOT, sha, _entries())


def test_pass_leaf_without_obligations_and_open_ledger_cannot_certify():
    case = _case()
    _leaf(case, 'C10.field_inp').update(status='PASS', evidence=[{'sha': HEAD}], obligations=[])
    with pytest.raises(ac.Rejected, match='pass_without_obligations'):
        ac.evaluate_case(case, ROOT, HEAD, _entries())
    entries = copy.deepcopy(_entries())
    forced = {'schema': 'x', 'claims': {k: {'statement': '', 'leaves': [{'id': k, 'status': 'PASS', 'obligations': ['DB-01'], 'evidence': [{'sha': HEAD}]}]} for k in CASE['claims']}}
    for entry in entries.values():
        entry['disposition'] = 'VERIFIED'
    verdict = ac.evaluate_case(forced, ROOT, HEAD, entries, 'pre_integration')
    assert verdict['C0'] == 'UNKNOWN' and verdict['technical_completion'] == 'UNKNOWN'
    entries['OPS-06']['disposition'] = None
    assert ac.evaluate_case(forced, ROOT, HEAD, entries, 'closed')['C0'] == 'UNKNOWN'
    entries['OPS-06']['disposition'] = 'VERIFIED'
    assert ac.evaluate_case(forced, ROOT, HEAD, entries, 'closed')['production_release'] == 'ELIGIBLE_NOT_DEPLOYED'


def test_evidence_file_with_other_bytes_is_rejected():
    case = _case()
    leaf = _leaf(case, 'C10.field_inp')
    leaf.update(status='PASS', evidence=[{'sha': HEAD, 'path': 'README.md', 'sha256': '0' * 64}], obligations=['WEB-03'])
    with pytest.raises(ac.Rejected, match='evidence_bytes'):
        ac.evaluate_case(case, ROOT, HEAD, _entries())


def test_a_failed_obligation_forbids_technical_closure_whatever_the_leaves_say():
    entries = copy.deepcopy(_entries())
    entries['DB-01']['disposition'] = 'FAILED'
    case = _case()
    for claim_id, claim in case['claims'].items():
        if claim_id in ac.TECHNICAL:
            for leaf in claim['leaves']:
                leaf.update(status='UNKNOWN')
    verdict = ac.evaluate_case(case, ROOT, HEAD, entries)
    assert verdict['technical_completion'] == 'FAIL' and verdict['failed_obligations'] == ['DB-01']


def test_threat_model_covers_every_endpoint_and_links_real_tests():
    model = json.loads((ROOT / 'assurance/threat-model.json').read_text(encoding='utf-8'))
    source = (ROOT / 'server/app.py').read_text(encoding='utf-8')
    import re
    endpoints = set(re.findall(r"self\.path\.split\('\?'\)\[0\] (?:==|!=) '(/[a-z/]+)'", source))
    assert endpoints == {'/api/config', '/api/health', '/api/lead'}, 'new endpoint: extend the threat model'
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
