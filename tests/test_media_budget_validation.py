"""Malformed policy must not certify an incomplete media inventory."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools import evidence_gate
from tools.media_budget import audit_media, parse_budget

ROOT = Path(__file__).resolve().parents[1]


def policy():
    return {'schema_version': 1, 'max_total_bytes': 30, 'max_single_asset_bytes': 20,
            'rules': [{'glob': '*.webp', 'min_count': 1, 'max_bytes': 12}]}


@pytest.fixture
def media(tmp_path):
    root = tmp_path / 'media'
    root.mkdir()
    (root / 'fixture.webp').write_bytes(b'x')
    return root


def test_canonical_integer_policy_accepts_actual_bytes(media):
    result = audit_media(media, policy())
    assert result['failures'] == []
    assert result['media_files'] == 1 and result['total_bytes'] == 1


@pytest.mark.parametrize('value', [None, [], {}, False, 'all'])
def test_required_rules_cannot_be_missing_empty_or_wrong_type(media, value):
    settings = policy()
    if value is None:
        del settings['rules']
    else:
        settings['rules'] = value
    assert audit_media(media, settings)['failures']


@pytest.mark.parametrize('key', ['schema_version', 'max_total_bytes', 'max_single_asset_bytes'])
def test_boolean_top_level_values_are_not_integer_budgets(media, key):
    settings = policy()
    settings[key] = True
    assert audit_media(media, settings)['failures']


@pytest.mark.parametrize('key', ['min_count', 'max_bytes'])
def test_boolean_rule_values_are_not_integer_budgets(media, key):
    settings = policy()
    settings['rules'][0][key] = True
    assert audit_media(media, settings)['failures']


@pytest.mark.parametrize('rule', [None, [], False, 1, 'all'])
def test_rule_entries_must_be_objects(media, rule):
    settings = policy()
    settings['rules'] = [rule]
    assert audit_media(media, settings)['failures']


@pytest.mark.parametrize('pattern', [None, True, 1, ['*.webp'], {'glob': '*.webp'}])
def test_pattern_must_be_a_relative_string(media, pattern):
    settings = policy()
    settings['rules'][0]['glob'] = pattern
    assert audit_media(media, settings)['failures']


@pytest.mark.parametrize('value', [0, -1, 1.5, '12', None])
def test_nonpositive_or_noninteger_limits_are_rejected(media, value):
    settings = policy()
    settings['rules'][0]['max_bytes'] = value
    assert audit_media(media, settings)['failures']


@pytest.mark.parametrize('duplicate', ['limit', 'rule'])
def test_cli_rejects_duplicate_policy_keys(media, tmp_path, duplicate):
    raw = json.dumps(policy())
    if duplicate == 'limit':
        raw = raw.replace('"max_total_bytes": 30', '"max_total_bytes": 0, "max_total_bytes": 30')
    else:
        raw = raw.replace('"min_count": 1', '"min_count": 2, "min_count": 1')
    budget = tmp_path / 'budget.json'
    budget.write_text(raw)
    report = tmp_path / 'report.json'
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'tools/media_budget.py'), '--root', str(media),
         '--budget', str(budget), '--report', str(report)],
        cwd=ROOT, capture_output=True, text=True, timeout=10, check=False)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert not report.exists(), 'Ambiguous policy must not publish a measurement report.'


@pytest.mark.parametrize('raw', ['[]', 'null', 'false', '12', '"policy"'])
def test_cli_rejects_nonobject_policy_without_a_traceback(media, tmp_path, raw):
    budget = tmp_path / 'budget.json'
    budget.write_text(raw)
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'tools/media_budget.py'), '--root', str(media),
         '--budget', str(budget), '--report', str(tmp_path / 'report.json')],
        cwd=ROOT, capture_output=True, text=True, timeout=10, check=False)
    assert proc.returncode == 1
    assert 'FAIL:' in proc.stderr and 'Traceback' not in proc.stderr


@pytest.mark.parametrize('constant', ['NaN', 'Infinity', '-Infinity'])
def test_policy_parser_rejects_nonfinite_json_numbers(constant):
    raw = json.dumps(policy()).replace('"max_total_bytes": 30', '"max_total_bytes": ' + constant)
    with pytest.raises(ValueError, match='Non-finite'):
        parse_budget(raw)


@pytest.mark.parametrize('duplicate', ['limit', 'rule'])
def test_independent_evidence_gate_rejects_ambiguous_budget(media, tmp_path, duplicate):
    raw = json.dumps(policy())
    if duplicate == 'limit':
        raw = raw.replace('"max_total_bytes": 30', '"max_total_bytes": 0, "max_total_bytes": 30')
    else:
        raw = raw.replace('"min_count": 1', '"min_count": 2, "min_count": 1')
    budget = tmp_path / 'budget.json'
    budget.write_text(raw)
    report = tmp_path / 'media.json'
    report.write_text(json.dumps(audit_media(media, policy())))
    result = evidence_gate.verify_evidence(tmp_path / 'shots', report, media, budget, 'a' * 40)
    assert any(str(budget) in failure and 'duplicate' in failure.lower()
               for failure in result['failures']), result


def test_policy_validation_does_not_change_canonical_thresholds(media):
    canonical = json.loads((ROOT / 'config/visual-budgets.json').read_text())
    before = copy.deepcopy(canonical)
    result = audit_media(media, canonical)
    assert canonical == before
    assert result['failures'], 'An undersized synthetic pack cannot pass real required categories.'
    assert canonical['max_total_bytes'] == 120000000
    assert canonical['max_single_asset_bytes'] == 10000000
