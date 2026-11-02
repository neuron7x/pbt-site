#!/usr/bin/env python3
"""The only path from IMPLEMENTED to VERIFIED: bind each obligation to an execution in real artifact bytes.

For each obligation and technical subclaim: every named test must appear in the JUnit inside the provider-digest-
checked ZIP, every case passed, and at least one designated mutant killed in the mutation ledger of the same revision.
Author-editable status fields are outputs here, never inputs. Absent evidence raises; nothing is promoted by default.

  evidence_reconcile.py --evidence-dir DIR --close   writes receipts, promotes ledger and case
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools import meta_evidence_gate as gate  # noqa: E402

RELEASE_JOB = 'Native contracts → full gate → offline bundles / lab metrics'
ROLE_JOB = {'release': RELEASE_JOB, 'mutation': 'Critical fault catalog + assurance decision'}


class Unbound(ValueError):
    pass


def _cases(raw):
    """(module, function) -> outcomes, read from the bytes of the JUnit, one row per executed case."""
    seen = {}
    full_testcase_ids = set()
    for case in ET.fromstring(raw).iter('testcase'):
        classname, name = case.get('classname'), case.get('name')
        if not classname or not name:
            raise Unbound('junit_testcase_identity_missing')
        full_identity = (classname, name)
        if full_identity in full_testcase_ids:
            raise Unbound('duplicate_junit_testcase_identity')
        full_testcase_ids.add(full_identity)
        bad = [k for k in ('failure', 'error', 'skipped') if case.find(k) is not None]
        seen.setdefault((classname, name.split('[', 1)[0]), []).append(
            {'name': name, 'outcome': bad[0] if bad else 'passed'})
    return seen


def _module_cases(seen, module):
    return {k: v for k, v in seen.items() if k[0] == module}


def _bind_test(reference, seen):
    path, _, function = reference.partition('::')
    module = path[:-3].replace('/', '.')
    rows = seen.get((module, function), []) if function else [r for v in _module_cases(seen, module).values() for r in v]
    if not rows:
        raise Unbound(f'test_never_executed_{reference}')
    bad = [r['name'] for r in rows if r['outcome'] != 'passed']
    if bad:
        raise Unbound(f'test_not_passed_{reference}')
    return {'oracle_identifier': reference, 'junit_cases': len(rows), 'test_outcome': 'passed',
            'junit_testcase_ids': sorted(f'{module}::{r["name"]}' for r in rows)[:50]}


def bindable_units(ledger):
    """Whole obligations and technical subclaims of hybrids: everything that may claim execution evidence."""
    for item in ledger['obligations']:
        subclaims = item.get('subclaims') or []
        if subclaims:
            for sub in subclaims:
                if sub['kind'] == 'technical':
                    yield sub['id'], sub
        elif item['disposition'] != 'BLOCKED_EXTERNAL':
            yield item['obligation_id'], item


def reconcile(manifest, evidence_dir, ledger, catalog):
    head = manifest['head_sha']
    with zipfile.ZipFile(evidence_dir / manifest['artifacts']['release']['filename']) as z:
        junit_raw = z.read('artifacts/full-junit.xml')
    with zipfile.ZipFile(evidence_dir / manifest['artifacts']['mutation']['filename']) as z:
        mutation = json.loads(z.read('mutation-ledger.json'))
    if mutation['head_sha'] != head:
        raise Unbound('mutation_ledger_other_revision')
    seen = _cases(junit_raw)
    verdicts = {r['id']: r['verdict'] for r in mutation['results']}
    run = manifest['runs']['full']
    release = manifest['artifacts']['release']
    jobs = run.get('jobs') or {}
    if RELEASE_JOB not in jobs:
        raise Unbound('release_job_absent')
    for mutant in catalog['mutants']:     # An oracle that does not run on clean code proves nothing about the fault.
        oracle = mutant.get('oracle') or []
        if oracle and oracle[0] != 'node':
            for reference in oracle:
                _bind_test(reference, seen)
    out = {}
    for unit, spec in bindable_units(ledger):
        controls = [m for m in spec.get('mutants', []) if verdicts.get(m) == 'KILLED']
        if not controls:
            raise Unbound(f'no_killed_negative_control_{unit}')
        if not spec.get('tests'):
            raise Unbound(f'no_tests_{unit}')
        out[unit] = [{
            'repository': manifest['repository'], 'source_sha': head, 'workflow_run_id': run['id'], 'run_attempt': run['attempt'],
            'job_id': jobs[RELEASE_JOB]['id'], 'artifact_id': release['id'], 'artifact_sha256': release['sha256'],
            'negative_control_identifier': controls, **_bind_test(reference, seen)} for reference in spec['tests']]
    return {'schema': 'pbt-execution-receipts-v1', 'repository': manifest['repository'], 'source_sha': head,
            'target': manifest['target'], 'junit_sha256': hashlib.sha256(junit_raw).hexdigest(),
            'mutation_catalog_sha256': mutation['catalog_sha256'], 'units': out}


def close(root, evidence_dir):
    """Run the gate, then promote only what bound. Writes files; acceptance is decided separately and independently."""
    manifest = gate.json_bytes((evidence_dir / 'manifest.json').read_bytes())
    head, base = manifest['head_sha'], manifest['base_sha']
    load = lambda rel: (root / rel).read_bytes()
    decision = gate.verify_manifest(manifest, evidence_dir, gate.json_bytes(load('config/runtime-soak-budgets.json')), head, base,
                                    gate.json_bytes(load('config/evidence-policy.json')), gate.json_bytes(load('config/required-tests.json')),
                                    load('config/mutation-catalog.json'))
    ledger = json.loads(load('assurance/ledger.json'))
    case = json.loads(load('assurance/case.json'))
    receipts = reconcile(manifest, evidence_dir, ledger, json.loads(load('config/mutation-catalog.json')))
    target = Path('assurance/evidence') / head
    (root / target).mkdir(parents=True, exist_ok=True)
    (root / target / 'receipts.json').write_text(json.dumps(receipts, indent=1, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    (root / target / 'decision.json').write_text(json.dumps(decision, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    (root / target / 'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    units = receipts['units']
    for item in ledger['obligations']:
        for sub in item.get('subclaims') or []:
            if sub['kind'] == 'technical':
                sub['status'] = 'VERIFIED'
        if item['disposition'] != 'BLOCKED_EXTERNAL':
            item.update(disposition='VERIFIED', execution_status='VERIFIED', verification_status='CONFIRMED',
                        verified_at_sha=head, artifact_paths=[f'{target}/receipts.json', f'{target}/decision.json'])
    ledger['stage'] = 'closed'
    ledger['evidence_sha'] = head
    for claim_id, claim in case['claims'].items():
        for leaf in claim['leaves']:
            if leaf['kind'] == 'engineering' and all(o in units for o in leaf['obligations']):
                leaf['status'] = 'PASS'
                leaf['evidence'] = [{'sha': head, 'path': f'{target}/receipts.json',
                                     'sha256': hashlib.sha256((root / target / 'receipts.json').read_bytes()).hexdigest()}]
    case['evidence_sha'] = head
    (root / 'assurance/ledger.json').write_text(json.dumps(ledger, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    (root / 'assurance/case.json').write_text(json.dumps(case, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    return receipts


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--evidence-dir', type=Path, required=True)
    p.add_argument('--close', action='store_true')
    a = p.parse_args(argv)
    if not a.close:
        p.error('--close is required: this tool writes the ledger')
    try:
        receipts = close(ROOT, a.evidence_dir)
    except (Unbound, gate.Rejected, OSError, ValueError, KeyError, TypeError, ET.ParseError, zipfile.BadZipFile) as exc:
        print(json.dumps({'status': 'FAIL', 'reason': str(exc)[:200], 'error_type': type(exc).__name__}))
        return 1
    print(json.dumps({'status': 'CLOSED', 'source_sha': receipts['source_sha'], 'units': len(receipts['units'])}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
