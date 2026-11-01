#!/usr/bin/env python3
"""Three-valued assurance decisions. Author-editable status fields are never accepted as evidence.

  (default)             SCHEMA_VALID        ledger and spec are well formed. Says nothing about the product.
  --require engineering ENGINEERING_ACCEPTED, or nonzero. Re-runs the verifier over real artifact ZIPs (--evidence-dir),
                        recomputes execution receipts, derives every claim from them, and checks the normative
                        specification and the proof's source are the ones that were measured.
  --require production  PRODUCTION_ELIGIBLE, or PRODUCTION_HOLD (exit 3). Adds owner-signed external receipts.
  EVIDENCE_REJECTED     (exit 1) something was forged, stale, missing or inconsistent.

Normal development only needs SCHEMA_VALID, so external facts being absent never makes CI red.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools import evidence_reconcile, external_receipts, meta_evidence_gate as gate  # noqa: E402

DISPOSITIONS = {'VERIFIED', 'BLOCKED_EXTERNAL', 'SUPERSEDED_WITH_PROOF', 'INAPPLICABLE_WITH_PROOF', 'FAILED'}
EXECUTION = {'PENDING', 'IN_PROGRESS', 'IMPLEMENTED', 'VERIFIED', 'BLOCKED'}
EVIDENTIAL = {'CONFIRMED', 'INFERRED', 'HYPOTHESIS', 'UNKNOWN', 'FALSIFIED'}
LEAF = {'PASS', 'FAIL', 'UNKNOWN'}
REQUIRED_FIELDS = ('obligation_id', 'source_revision', 'source_location', 'defect_or_requirement', 'evidence_class',
                   'risk_and_impact', 'preconditions', 'formal_invariant', 'counterexample', 'test_oracle', 'required_change',
                   'dependency_ids', 'verification_commands', 'acceptance_predicate', 'artifact_paths', 'execution_status',
                   'verification_status', 'disposition')
TECHNICAL = tuple(f'C{i}' for i in range(1, 10))
# NORMATIVE_SPECIFICATION: the source tasks, pinned here so they cannot move with the evidence that cites them.
NORMATIVE_DIGESTS = {
    'assurance/source/tasks.json': '6782e98ceb19235e1008b372f4d72135782145cd13a79b3966294261ce795fda',
    'assurance/source/risks.json': '38a77122733ccde8fed759b06110780967771237d6ec0a3bf04134a6d175830d',
    'assurance/source/gates.json': 'ddffb64eab63d28f718f3e428847e996fce58578acfde56cf21c2ede04f0f2a4',
    'assurance/source/owner_decisions.json': 'e5e750f58f99d629d6b3c06eea2e40598d349231b4203aae60050a6bbc24b774',
}
# EVIDENCE and reports only. Tests, tools, config, threat model and specification are not here: changing any of
# them after measurement voids the proof.
PROOF_COMPATIBLE = ('assurance/evidence/', 'assurance/ledger.json', 'assurance/case.json', 'docs/', 'README.md')
# In the ledger and case, only these may differ from the measured revision: the outcome of the promotion.
LEDGER_MUTABLE = {'disposition', 'execution_status', 'verification_status', 'verified_at_sha', 'artifact_paths', 'status'}
CASE_MUTABLE = {'status', 'evidence'}


class Rejected(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise Rejected(code)


def _test_exists(root, reference):
    path, _, name = reference.partition('::')
    file = root / path
    # A test file, not any file that happens to exist. Existence says nothing about execution: see reconcile.
    if not re.fullmatch(r'tests/test_[A-Za-z0-9_]+\.py', path) or not file.is_file():
        return False
    if not name:
        return True
    return re.search(rf'^\s*def {re.escape(name)}\(', file.read_text(encoding='utf-8'), re.M) is not None


def check_spec(tasks):
    ids = [t['id'] for t in tasks]
    require(len(ids) == len(set(ids)), 'spec_duplicate_task')
    known = set(ids)
    graph = {t['id']: t['dependencies'] for t in tasks}
    for task, deps in graph.items():
        for dep in deps:
            require(dep in known, f'spec_missing_dependency_{task}_{dep}')
    state = {}

    def walk(node):
        require(state.get(node) != 'open', f'spec_dependency_cycle_{node}')
        if state.get(node) == 'done':
            return
        state[node] = 'open'
        for dep in graph[node]:
            walk(dep)
        state[node] = 'done'
    for node in graph:
        walk(node)


def check_normative(root):
    for rel, digest in NORMATIVE_DIGESTS.items():
        require(hashlib.sha256((root / rel).read_bytes()).hexdigest() == digest, f'normative_specification_changed_{rel}')


def _check_unit_refs(unit, spec, root, catalog_ids):
    for reference in spec.get('tests', []):
        require(_test_exists(root, reference), f'{unit}_names_absent_test_{reference}')
    for mutant in spec.get('mutants', []):
        require(mutant in catalog_ids, f'{unit}_names_absent_mutant_{mutant}')


def check_ledger(ledger, tasks, root, catalog_ids=(), external_classes=()):
    known = {t['id']: t for t in tasks}
    entries = {}
    for item in ledger['obligations']:
        require(item['obligation_id'] not in entries, f"duplicate_obligation_{item['obligation_id']}")
        entries[item['obligation_id']] = item
    require(set(entries) == set(known), f'obligation_set_differs_{sorted(set(known) ^ set(entries))[:5]}')
    require(ledger['stage'] in ('pre_integration', 'closed'), 'unknown_stage')
    final = ledger['stage'] == 'closed'
    for oid, item in entries.items():
        for field in REQUIRED_FIELDS:
            require(field in item, f'{oid}_missing_{field}')
        task = known[oid]
        # The acceptance contract is copied from the specification and cannot be weakened in the ledger.
        for mine, theirs in (('formal_invariant', 'invariant'), ('acceptance_predicate', 'acceptance'),
                             ('counterexample', 'red_test'), ('dependency_ids', 'dependencies')):
            require(item[mine] == task[theirs], f'{oid}_contract_differs_from_specification_{mine}')
        require(item['execution_status'] in EXECUTION, f'{oid}_execution_status')
        require(item['verification_status'] in EVIDENTIAL, f'{oid}_verification_status')
        disposition = item['disposition']
        if final:
            require(disposition in DISPOSITIONS, f'{oid}_needs_final_disposition')
        else:
            require(disposition is None or disposition in DISPOSITIONS, f'{oid}_disposition')
        _check_unit_refs(oid, item, root, catalog_ids)
        subclaims = item.get('subclaims') or []
        for sub in subclaims:
            require(sub['id'].startswith(oid + '.') and sub['kind'] in ('technical', 'external'), f'{oid}_subclaim_shape')
            if sub['kind'] == 'technical':
                require(sub.get('tests') and sub.get('mutants'), f"{sub['id']}_technical_needs_tests_and_mutants")
                _check_unit_refs(sub['id'], sub, root, catalog_ids)
            else:
                require(sub.get('classes') and set(sub['classes']) <= set(external_classes), f"{sub['id']}_external_class")
        if disposition == 'VERIFIED':
            require(item['tests'], f'{oid}_verified_without_tests')
            require(item['verification_status'] == 'CONFIRMED' and item['execution_status'] == 'VERIFIED', f'{oid}_verified_but_not_confirmed')
            require(item.get('verified_at_sha') and item['artifact_paths'], f'{oid}_verified_without_execution_reference')
            require(task['external_prerequisite'] is False or item.get('external_receipt'), f'{oid}_verified_without_external_receipt')
            for dep in item['dependency_ids']:
                other = entries[dep]
                ok = other['disposition'] == 'VERIFIED' or any(s['kind'] == 'technical' for s in other.get('subclaims') or [])
                require(ok, f'{oid}_verified_over_unverified_dependency_{dep}')
        if disposition == 'BLOCKED_EXTERNAL':
            require(item.get('blocker'), f'{oid}_blocked_without_named_blocker')
            require(item['execution_status'] == 'BLOCKED' and item['verification_status'] == 'UNKNOWN', f'{oid}_blocked_transition')
            if task['external_prerequisite'] is False:
                # The specification says this is internal. Only a split with a stated reason may hold it externally.
                kinds = {s['kind'] for s in subclaims}
                require({'technical', 'external'} <= kinds and item.get('reclassification_reason'), f'{oid}_reclassified_without_split')
        if disposition in ('SUPERSEDED_WITH_PROOF', 'INAPPLICABLE_WITH_PROOF'):
            require(item.get('proof'), f'{oid}_disposition_without_proof')
    return entries


def decide_claim(leaves):
    if not leaves or any(s not in LEAF for s in leaves):
        return 'UNKNOWN'
    if 'FAIL' in leaves:
        return 'FAIL'
    if any(s != 'PASS' for s in leaves):
        return 'UNKNOWN'
    return 'PASS'


def _git(root, *args):
    return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True, timeout=30).stdout


def _strip(value, mutable):
    if isinstance(value, dict):
        return {k: _strip(v, mutable) for k, v in value.items() if k not in mutable}
    if isinstance(value, list):
        return [_strip(v, mutable) for v in value]
    return value


def check_proof_source(root, evidence_sha, target_sha):
    """Evidence stays valid only if the target adds reports on top of the measured revision, nothing else."""
    for sha in (evidence_sha, target_sha):
        require(isinstance(sha, str) and re.fullmatch(r'[0-9a-f]{40}', sha or ''), 'stale_evidence_sha')
    try:
        _git(root, 'merge-base', '--is-ancestor', evidence_sha, target_sha)
        changed = _git(root, 'diff', '--name-only', evidence_sha, target_sha).decode().split()
    except (OSError, subprocess.SubprocessError):
        raise Rejected('stale_evidence_sha') from None
    for path in changed:
        require(path.startswith(PROOF_COMPATIBLE), f'proof_void_changed_{path}')
    measured_ledger = json.loads(_git(root, 'show', f'{evidence_sha}:assurance/ledger.json'))
    measured_case = json.loads(_git(root, 'show', f'{evidence_sha}:assurance/case.json'))
    target_ledger = json.loads(_git(root, 'show', f'{target_sha}:assurance/ledger.json'))
    target_case = json.loads(_git(root, 'show', f'{target_sha}:assurance/case.json'))
    drop = {'stage', 'evidence_sha'}
    require(_strip(measured_ledger, LEDGER_MUTABLE | drop) == _strip(target_ledger, LEDGER_MUTABLE | drop), 'ledger_contract_changed_after_measurement')
    require(_strip(measured_case, CASE_MUTABLE | drop) == _strip(target_case, CASE_MUTABLE | drop), 'case_structure_changed_after_measurement')
    return target_ledger, target_case


def derive_claims(case, units, external):
    """Leaves come from receipts and signatures. A status in the file must agree, it is never the reason."""
    claims = {}
    policy_leaves = external['leaves']
    for claim_id, claim in case['claims'].items():
        statuses = []
        for leaf in claim['leaves']:
            if leaf['kind'] == 'engineering':
                derived = 'PASS' if leaf['obligations'] and all(o in units for o in leaf['obligations']) else 'UNKNOWN'
            else:
                classes = policy_leaves.get(leaf['id'], [])
                derived = 'PASS' if classes and all(external['status'].get(c) == 'PASS' for c in classes) else 'UNKNOWN'
            require(leaf['status'] in LEAF, f"{leaf['id']}_status")
            require(leaf['status'] != 'PASS' or derived == 'PASS', f"{leaf['id']}_claims_pass_without_derivation")
            statuses.append(derived)
        claims[claim_id] = decide_claim(statuses)
    require(set(claims) == {f'C{i}' for i in range(1, 11)}, 'claim_set')
    return claims


def _load(root, rel):
    return json.loads((root / rel).read_text(encoding='utf-8'))



def check_committed_controls(root, target_sha):
    """Reject working-tree changes to inputs that decide release eligibility.

    CI artifacts live outside this tree, but release-control policy, case topology,
    the signer trust root, and external receipts must match the evaluated commit.
    GitHub/CI provenance must still be verified separately.
    """
    require(isinstance(target_sha, str) and re.fullmatch(r'[0-9a-f]{40}', target_sha),
            'invalid_acceptance_target_sha')
    controls = (
        'assurance/ledger.json',
        'assurance/case.json',
        'config/external-evidence-policy.json',
        'config/owner-allowed-signers',
    )
    for rel in controls:
        try:
            committed = _git(root, 'show', f'{target_sha}:{rel}')
            actual = (root / rel).read_bytes()
        except (OSError, subprocess.SubprocessError):
            raise Rejected(f'acceptance_control_missing_from_target_{rel}') from None
        require(actual == committed, f'acceptance_control_dirty_{rel}')

    external_dir = 'assurance/evidence/external'
    try:
        committed_files = set(_git(root, 'ls-tree', '-r', '--name-only', target_sha,
                                   '--', external_dir).decode().splitlines())
    except (OSError, subprocess.SubprocessError):
        raise Rejected('external_receipt_tree_unavailable') from None
    directory = root / external_dir
    actual_files = ({p.relative_to(root).as_posix() for p in directory.rglob('*') if p.is_file()}
                    if directory.is_dir() else set())
    require(actual_files == committed_files, 'external_receipt_set_not_at_target')
    for rel in sorted(committed_files):
        try:
            committed = _git(root, 'show', f'{target_sha}:{rel}')
            actual = (root / rel).read_bytes()
        except (OSError, subprocess.SubprocessError):
            raise Rejected(f'external_receipt_unavailable_{rel}') from None
        require(actual == committed, f'external_receipt_dirty_{rel}')


def schema_check(root):
    check_normative(root)
    tasks = _load(root, 'assurance/source/tasks.json')
    check_spec(tasks)
    catalog = {m['id'] for m in _load(root, 'config/mutation-catalog.json')['mutants']}
    classes = set(_load(root, 'config/external-evidence-policy.json')['classes'])
    return check_ledger(_load(root, 'assurance/ledger.json'), tasks, root, catalog, classes)


def accept_engineering(root, target_sha, evidence_dir):
    check_committed_controls(root, target_sha)
    entries = schema_check(root)
    ledger_file = _load(root, 'assurance/ledger.json')
    case_file = _load(root, 'assurance/case.json')
    require(evidence_dir is not None, 'no_execution_evidence_supplied')
    require(ledger_file['stage'] == 'closed', 'ledger_not_closed')
    evidence_sha = ledger_file.get('evidence_sha')
    require(evidence_sha == case_file.get('evidence_sha'), 'evidence_sha_disagrees')
    check_proof_source(root, evidence_sha, target_sha)
    manifest = gate.json_bytes((evidence_dir / 'manifest.json').read_bytes())
    require(manifest['head_sha'] == evidence_sha, 'evidence_for_other_revision')
    require(manifest['target']['kind'] in ('push', 'workflow_dispatch'), 'evidence_not_from_main')
    read = lambda rel: _git(root, 'show', f'{evidence_sha}:{rel}')     # Policies as they were measured, not as edited since.
    decision = gate.verify_manifest(manifest, evidence_dir, gate.json_bytes(read('config/runtime-soak-budgets.json')), evidence_sha,
                                    manifest['base_sha'], gate.json_bytes(read('config/evidence-policy.json')),
                                    gate.json_bytes(read('config/required-tests.json')), read('config/mutation-catalog.json'))
    recomputed = evidence_reconcile.reconcile(manifest, evidence_dir, ledger_file, json.loads(read('config/mutation-catalog.json')))
    committed = _load(root, f'assurance/evidence/{evidence_sha}/receipts.json')
    require(committed == recomputed, 'committed_receipts_differ_from_artifact_bytes')
    units = recomputed['units']
    for oid, entry in entries.items():
        if entry['disposition'] == 'VERIFIED':
            require(oid in units, f'{oid}_verified_without_execution_receipt')
    failed = sorted(o for o, e in entries.items() if e['disposition'] == 'FAILED')
    require(not failed, f'failed_obligations_{failed}')
    policy = _load(root, 'config/external-evidence-policy.json')
    leaves = {}
    for class_id, rule in policy['classes'].items():
        leaves.setdefault(rule['leaf'], []).append(class_id)
    external = {'status': external_receipts.status_all(root, target_sha), 'leaves': leaves}
    claims = derive_claims(case_file, units, external)
    technical = decide_claim([claims[c] for c in TECHNICAL])
    require(technical == 'PASS', f'technical_claims_{technical}_{[c for c in TECHNICAL if claims[c] != "PASS"]}')
    dispositions = {}
    for entry in entries.values():
        dispositions[entry['disposition']] = dispositions.get(entry['disposition'], 0) + 1
    return {'schema': 'pbt-assurance-decision-v2', 'target_sha': target_sha, 'evidence_sha': evidence_sha, 'claims': claims,
            'technical_completion': technical, 'gate': decision['status'], 'junit_tests': decision['junit_tests'],
            'mutation': decision['mutation'], 'external': external['status'], 'dispositions': dispositions,
            'bound_units': len(units), 'C0': decide_claim(list(claims.values())),
            'scope': 'declared envelope in docs/ASSURANCE.md; finite tests; provider API as root of trust'}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--target-sha', default=None)
    p.add_argument('--require', choices=('schema', 'engineering', 'production'), default='schema')
    p.add_argument('--evidence-dir', type=Path, default=None)
    p.add_argument('--out', type=Path, default=None)
    a = p.parse_args(argv)
    code = 0
    try:
        if a.require == 'schema':
            entries = schema_check(a.root)
            result = {'decision': 'SCHEMA_VALID', 'obligations': len(entries),
                      'note': 'Well-formed only. Not an acceptance of anything.'}
        else:
            target = a.target_sha or _git(a.root, 'rev-parse', 'HEAD').decode().strip()
            result = accept_engineering(a.root, target, a.evidence_dir)
            result['decision'] = 'ENGINEERING_ACCEPTED'
            if a.require == 'production':
                eligible = result['C0'] == 'PASS'
                result['decision'] = 'PRODUCTION_ELIGIBLE' if eligible else 'PRODUCTION_HOLD'
                code = 0 if eligible else 3
    except (Rejected, gate.Rejected, evidence_reconcile.Unbound, OSError, ValueError, KeyError, TypeError, IndexError,
            ET.ParseError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        result, code = {'decision': 'EVIDENCE_REJECTED', 'reason': str(exc)[:240], 'error_type': type(exc).__name__}, 1
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(result, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == '__main__':
    sys.exit(main())
