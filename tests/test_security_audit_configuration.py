"""Fail-closed structural guard for the dependency-audit workflow.

These assertions inspect the supported workflow's exact step structure; they
are not a general YAML parser or a security scanner. Both scans for each lock
are guarded independently, so one valid step cannot mask a disabled scan.
"""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parent.parent
PIN = 'pypa/gh-action-pip-audit@1220774d901786e6f652ae159f7b6bc8fea6d266'
AUDIT_FIELDS = [
    f'        uses: {PIN}',
    '        with:',
    '          inputs: requirements.txt',
    '          no-deps: true',
    '          require-hashes: true',
    '          vulnerability-service: osv',
]
AUDIT_FIELDS_SAST = [v.replace('inputs: requirements.txt', 'inputs: requirements-sast.txt')
                     for v in AUDIT_FIELDS]


def dependency_steps(workflow):
    assert workflow.count('  dependency-audit:\n') == 1
    assert workflow.count('\n  scoped-static:\n') == 1
    job = workflow.split('  dependency-audit:\n', 1)[1].split('\n  scoped-static:\n', 1)[0]
    blocks = re.split(r'(?=^      - name: )', job, flags=re.MULTILINE)[1:]
    assert blocks
    return [[line.rstrip() for line in block.splitlines()
             if line.strip() and not line.lstrip().startswith('#')] for block in blocks]


def find_single_id(steps, ident):
    matches = [i for i, step in enumerate(steps) if f'        id: {ident}' in step]
    assert len(matches) == 1, f'expected one {ident} step'
    return matches[0]


def assert_audit_policy(workflow):
    steps = dependency_steps(workflow)
    first = find_single_id(steps, 'audit')
    complete = find_single_id(steps, 'complete_audit')
    assert steps[first] == [
        '      - name: Audit hash-locked requirements against OSV; no suppressions',
        '        id: audit', *AUDIT_FIELDS,
    ]
    assert steps[complete] == [
        '      - name: Audit every pinned requirement and emit JSON',
        '        id: complete_audit', *AUDIT_FIELDS,
        '          internal-be-careful-extra-flags: --format=json --disable-pip',
    ]
    sast_first = find_single_id(steps, 'sast_audit')
    sast_complete = find_single_id(steps, 'sast_complete_audit')
    assert steps[sast_first] == [
        '      - name: Audit hash-locked SAST scanner requirements against OSV',
        '        id: sast_audit', *AUDIT_FIELDS_SAST,
    ]
    assert steps[sast_complete] == [
        '      - name: Audit every pinned SAST scanner requirement and emit JSON',
        '        id: sast_complete_audit', *AUDIT_FIELDS_SAST,
        '          internal-be-careful-extra-flags: --format=json --disable-pip',
    ]
    cleanup = [i for i, step in enumerate(steps)
               if any(line.strip().endswith('rm -f /tmp/pip-audit-output.txt') for line in step)]
    assert cleanup == [first - 1, complete - 1, sast_first - 1, sast_complete - 1]
    assert first < complete < sast_first < sast_complete
    assert steps[cleanup[0]] == [
        '      - name: Remove any stale runner-local audit output',
        '        run: rm -f /tmp/pip-audit-output.txt',
    ]
    assert steps[cleanup[1]] == [
        '      - name: Remove first audit output before complete pinned-input scan',
        '        run: |',
        '          test "$(git rev-parse HEAD)" = "$PBT_HEAD_SHA"',
        '          git show "${PBT_HEAD_SHA}:requirements.txt" | cmp - requirements.txt',
        '          rm -f /tmp/pip-audit-output.txt',
    ]
    assert steps[cleanup[2]] == [
        '      - name: Remove primary output before SAST lock baseline scan',
        '        run: |',
        '          test "$(git rev-parse HEAD)" = "$PBT_HEAD_SHA"',
        '          git show "${PBT_HEAD_SHA}:requirements-sast.txt" | cmp - requirements-sast.txt',
        '          rm -f /tmp/pip-audit-output.txt',
    ]
    assert steps[cleanup[3]] == [
        '      - name: Remove SAST baseline output before complete locked-input scan',
        '        run: |',
        '          test "$(git rev-parse HEAD)" = "$PBT_HEAD_SHA"',
        '          git show "${PBT_HEAD_SHA}:requirements-sast.txt" | cmp - requirements-sast.txt',
        '          rm -f /tmp/pip-audit-output.txt',
    ]
    provenance = [step for step in steps if step[0] ==
                  '      - name: Exact source provenance and diff hygiene']
    assert provenance == [[
        '      - name: Exact source provenance and diff hygiene',
        '        run: |',
        '          test "$(git rev-parse HEAD)" = "$PBT_HEAD_SHA"',
        '          git show "${PBT_HEAD_SHA}:requirements.txt" | cmp - requirements.txt',
        '          git diff --check HEAD^1 HEAD',
    ]]
    assert workflow.count(f'uses: {PIN}') == 4
    assert 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1' in workflow
    assert 'actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0' in workflow
    assert 'python tools/security_receipt.py --requirements requirements.txt' in workflow
    assert '--report /tmp/pip-audit-output.txt --output artifacts/security/osv-receipt.json' in workflow
    assert 'python tools/security_receipt.py --requirements requirements-sast.txt' in workflow
    assert '--report /tmp/pip-audit-output.txt --output artifacts/security/osv-sast-receipt.json' in workflow
    assert 'AUDIT_OUTCOME: ${{ steps.sast_complete_audit.outcome }}' in workflow
    assert 'AUDIT_BASELINE_OUTCOME: ${{ steps.sast_audit.outcome }}' in workflow
    assert workflow.count('            artifacts/security/osv-sast-receipt.json') == 1
    assert workflow.index('id: complete_audit') < workflow.index('python tools/security_receipt.py')
    assert 'AUDIT_OUTCOME: ${{ steps.complete_audit.outcome }}' in workflow
    assert 'AUDIT_BASELINE_OUTCOME: ${{ steps.audit.outcome }}' in workflow
    assert 'if-no-files-found: error' in workflow
    assert 'continue-on-error:' not in workflow
    assert 'ignore-vulns:' not in workflow
    assert 'internal-be-careful-allow-failure:' not in workflow
    assert "  pull_request:\n    branches: [main]\n" in workflow
    assert "  push:\n    branches: [main]\n" in workflow
    assert 'git rev-parse HEAD' in workflow
    assert 'head.sha' in workflow


def test_dependency_audit_is_sha_pinned_and_cannot_ignore_failures():
    assert_audit_policy((ROOT / '.github/workflows/security-assurance.yml').read_text())


@pytest.mark.parametrize('step_id', ['audit', 'complete_audit'])
@pytest.mark.parametrize('original,replacement', [
    ('uses: ' + PIN, 'uses: pypa/gh-action-pip-audit@v1.1.0'),
    ('inputs: requirements.txt', 'inputs: another-requirements.txt'),
    ('no-deps: true', 'no-deps: false'),
    ('require-hashes: true', 'require-hashes: false'),
    ('vulnerability-service: osv', 'vulnerability-service: pypi'),
    ('vulnerability-service: osv', ''),
])
def test_per_step_mutants_cannot_be_masked_by_other_step(step_id, original, replacement):
    workflow = (ROOT / '.github/workflows/security-assurance.yml').read_text()
    marker = f'        id: {step_id}\n'
    start = workflow.index(marker)
    end = workflow.find('\n      - name:', start)
    step = workflow[start:end]
    assert original in step
    mutant = workflow[:start] + step.replace(original, replacement, 1) + workflow[end:]
    with pytest.raises(AssertionError):
        assert_audit_policy(mutant)


def test_complete_scan_without_full_coverage_flags_is_rejected():
    workflow = (ROOT / '.github/workflows/security-assurance.yml').read_text()
    mutant = workflow.replace('internal-be-careful-extra-flags: --format=json --disable-pip',
                              'internal-be-careful-extra-flags: --format=json')
    assert mutant != workflow
    with pytest.raises(AssertionError):
        assert_audit_policy(mutant)


def test_action_condition_cannot_disable_one_scan():
    workflow = (ROOT / '.github/workflows/security-assurance.yml').read_text()
    mutant = workflow.replace('        id: complete_audit\n',
                              '        id: complete_audit\n        if: false\n')
    with pytest.raises(AssertionError):
        assert_audit_policy(mutant)


@pytest.mark.parametrize('which', [0, 1])
def test_removing_either_pre_scan_blob_check_fails_policy(which):
    workflow = (ROOT / '.github/workflows/security-assurance.yml').read_text()
    check = '          git show "${PBT_HEAD_SHA}:requirements.txt" | cmp - requirements.txt\n'
    parts = workflow.split(check)
    assert len(parts) == 3
    mutant = parts[0] + ('' if which == 0 else check) + parts[1] + ('' if which == 1 else check) + parts[2]
    with pytest.raises(AssertionError):
        assert_audit_policy(mutant)

@pytest.mark.parametrize('step_id', ['sast_audit', 'sast_complete_audit'])
@pytest.mark.parametrize('original,replacement', [
    ('uses: ' + PIN, 'uses: pypa/gh-action-pip-audit@v2'),
    ('inputs: requirements-sast.txt', 'inputs: requirements.txt'),
    ('no-deps: true', 'no-deps: false'),
    ('require-hashes: true', 'require-hashes: false'),
    ('vulnerability-service: osv', 'vulnerability-service: pypi'),
])
def test_sast_each_scan_rejects_weakened_configuration(step_id, original, replacement):
    workflow = (ROOT / '.github/workflows/security-assurance.yml').read_text()
    marker = f'        id: {step_id}\n'
    start = workflow.index(marker)
    end = workflow.find('\n      - name:', start)
    block = workflow[start:end]
    assert original in block
    altered = workflow[:start] + block.replace(original, replacement, 1) + workflow[end:]
    with pytest.raises(AssertionError):
        assert_audit_policy(altered)


def test_sast_scan_disappearance_cannot_hide_behind_primary_clean_result():
    workflow = (ROOT / '.github/workflows/security-assurance.yml').read_text()
    altered = workflow.replace('        id: sast_complete_audit', '        id: disabled_sast_complete', 1)
    with pytest.raises(AssertionError):
        assert_audit_policy(altered)


def test_sast_receipt_cannot_be_silently_omitted():
    workflow = (ROOT / '.github/workflows/security-assurance.yml').read_text()
    altered = workflow.replace('            artifacts/security/osv-sast-receipt.json\n', '', 1)
    with pytest.raises(AssertionError):
        assert_audit_policy(altered)
