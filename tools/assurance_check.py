#!/usr/bin/env python3
"""Validate the obligation ledger and decide the release case in three-valued logic. No scores, no averages.

  PASS only if every mandatory leaf is PASS. Any FAIL is FAIL. Otherwise UNKNOWN.

Technical completion (C1-C9) and production release (C0, needs C10) are separate verdicts. Green CI is
never an input to C10. A VERIFIED obligation must name tests that exist in the tree; a task the source
registry marks as needing an external receipt can only become VERIFIED by pointing at that receipt.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
DISPOSITIONS = {'VERIFIED', 'BLOCKED_EXTERNAL', 'SUPERSEDED_WITH_PROOF', 'INAPPLICABLE_WITH_PROOF', 'FAILED'}
EXECUTION = {'PENDING', 'IN_PROGRESS', 'IMPLEMENTED', 'VERIFIED', 'BLOCKED'}
EVIDENTIAL = {'CONFIRMED', 'INFERRED', 'HYPOTHESIS', 'UNKNOWN', 'FALSIFIED'}
LEAF = {'PASS', 'FAIL', 'UNKNOWN'}
REQUIRED_FIELDS = ('obligation_id', 'source_revision', 'source_location', 'defect_or_requirement', 'evidence_class',
                   'risk_and_impact', 'preconditions', 'formal_invariant', 'counterexample', 'test_oracle', 'required_change',
                   'dependency_ids', 'verification_commands', 'acceptance_predicate', 'artifact_paths', 'execution_status',
                   'verification_status', 'disposition')
TECHNICAL = tuple(f'C{i}' for i in range(1, 10))
# After proof at evidence_sha, only these may change without invalidating it. Nothing executable.
PROOF_COMPATIBLE = ('assurance/', 'docs/', 'README.md')


class Rejected(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise Rejected(code)


def _test_exists(root, reference):
    path, _, name = reference.partition('::')
    file = root / path
    if not file.is_file():
        return False
    if not name:
        return True
    return re.search(rf'^\s*def {re.escape(name)}\(', file.read_text(encoding='utf-8'), re.M) is not None


def check_ledger(ledger, tasks, root, catalog_ids=()):
    known = {t['id']: t for t in tasks}
    entries = {}
    for item in ledger['obligations']:
        require(item['obligation_id'] not in entries, f"duplicate_obligation_{item['obligation_id']}")
        entries[item['obligation_id']] = item
    require(set(entries) == set(known), f'obligation_set_differs_{sorted(set(known) ^ set(entries))[:5]}')
    final = ledger['stage'] == 'closed'
    require(ledger['stage'] in ('pre_integration', 'closed'), 'unknown_stage')
    for oid, item in entries.items():
        for field in REQUIRED_FIELDS:
            require(field in item, f'{oid}_missing_{field}')
        require(item['execution_status'] in EXECUTION, f'{oid}_execution_status')
        require(item['verification_status'] in EVIDENTIAL, f'{oid}_verification_status')
        disposition = item['disposition']
        if final:
            require(disposition in DISPOSITIONS, f'{oid}_needs_final_disposition')
        else:
            require(disposition is None or disposition in DISPOSITIONS, f'{oid}_disposition')
        for reference in item.get('tests', []):
            require(_test_exists(root, reference), f'{oid}_names_absent_test_{reference}')
        for mutant in item.get('mutants', []):
            require(mutant in catalog_ids, f'{oid}_names_absent_mutant_{mutant}')
        if disposition == 'VERIFIED':
            require(item['tests'], f'{oid}_verified_without_tests')
            require(item['verification_status'] == 'CONFIRMED', f'{oid}_verified_but_not_confirmed')
            require(known[oid]['external_prerequisite'] is False or item.get('external_receipt'), f'{oid}_verified_without_external_receipt')
        if disposition == 'BLOCKED_EXTERNAL':
            require(item.get('blocker'), f'{oid}_blocked_without_named_blocker')
        if disposition in ('SUPERSEDED_WITH_PROOF', 'INAPPLICABLE_WITH_PROOF'):
            require(item.get('proof'), f'{oid}_disposition_without_proof')
    return entries


def _proof_compatible(root, evidence_sha, target_sha):
    if evidence_sha == target_sha:
        return True
    try:
        changed = subprocess.run(['git', 'diff', '--name-only', evidence_sha, target_sha], cwd=root, check=True,
                                 capture_output=True, text=True, timeout=20).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return False
    return all(c.startswith(PROOF_COMPATIBLE) for c in changed)


def decide_claim(leaves):
    if not leaves or any(s not in LEAF for s in leaves):
        return 'UNKNOWN'
    if 'FAIL' in leaves:
        return 'FAIL'
    if any(s != 'PASS' for s in leaves):
        return 'UNKNOWN'
    return 'PASS'


def evaluate_case(case, root, target_sha, entries):
    claims = {}
    for claim_id, claim in case['claims'].items():
        statuses = []
        for leaf in claim['leaves']:
            status = leaf['status']
            require(status in LEAF, f"{leaf['id']}_status")
            if status == 'PASS':
                require(leaf.get('evidence'), f"{leaf['id']}_pass_without_evidence")
                for ref in leaf['evidence']:
                    require(_proof_compatible(root, ref['sha'], target_sha), f"{leaf['id']}_stale_evidence_sha")
                    if 'path' in ref:
                        file = root / ref['path']
                        require(file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest() == ref['sha256'],
                                f"{leaf['id']}_evidence_bytes")
                for oid in leaf.get('obligations', []):
                    require(entries[oid]['disposition'] == 'VERIFIED', f"{leaf['id']}_obligation_{oid}_not_verified")
            statuses.append(status)
        claims[claim_id] = decide_claim(statuses)
    require(set(claims) == {f'C{i}' for i in range(1, 11)}, 'claim_set')
    failed = sorted(o for o, e in entries.items() if e['disposition'] == 'FAILED')
    technical = decide_claim([claims[c] for c in TECHNICAL])
    if failed:
        technical = 'FAIL'
    overall = decide_claim(list(claims.values()))
    if failed:
        overall = 'FAIL'
    verdict = {'schema': 'pbt-assurance-decision-v1', 'target_sha': target_sha, 'claims': claims, 'failed_obligations': failed,
               'technical_completion': technical, 'C0': overall,
               'production_release': 'ELIGIBLE_NOT_DEPLOYED' if overall == 'PASS' else 'PRODUCTION HOLD',
               'dispositions': {}}
    for entry in entries.values():
        key = entry['disposition'] or 'UNSET'
        verdict['dispositions'][key] = verdict['dispositions'].get(key, 0) + 1
    return verdict


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--target-sha', default=None)
    p.add_argument('--out', type=Path, default=None)
    a = p.parse_args(argv)
    root = a.root
    try:
        load = lambda rel: json.loads((root / rel).read_text(encoding='utf-8'))
        target = a.target_sha or subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
        catalog = {m['id'] for m in load('config/mutation-catalog.json')['mutants']}
        entries = check_ledger(load('assurance/ledger.json'), load('assurance/source/tasks.json'), root, catalog)
        result = evaluate_case(load('assurance/case.json'), root, target, entries)
    except (Rejected, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'FAIL', 'reason': str(exc)[:200], 'error_type': type(exc).__name__}))
        return 1
    result['status'] = 'VALID'
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(result, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
