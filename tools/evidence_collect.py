#!/usr/bin/env python3
"""Fetch one target's workflow receipts and artifact bytes from the GitHub API into a v2 manifest.

Separation of duties: this producer never reads a PASS field. It binds each ZIP to the digest GitHub
itself reports for that artifact id, refetched immediately before use, so a manifest cannot select its
own digest. tools/meta_evidence_gate.py then judges the bytes offline, with no network and no gh.

A GitHub API answer authenticated by the operator's token is the root of trust here; nothing is signed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

WORKFLOW_ROLE = {
    'PBT / Перевірка якості PR': 'full',
    'PBT / Transport reliability gate': 'transport',
    'PBT / Доказовий дизайн та медіабюджет': 'visual',
    'PBT / Vulnerability assurance (locked Python dependencies)': 'security',
    'PBT / 30-minute runtime soak — measured synthetic R2/R3 evidence': 'soak',
}
ARTIFACT_PREFIX = {
    'release': ('full', 'pbt-release-'), 'baseline': ('full', 'pbt-main-baseline-'),
    'mobile': ('full', 'pbt-mobile-lab-'), 'http': ('transport', 'pbt-http-'),
    'visual': ('visual', 'pbt-visual-proof-'), 'osv': ('security', 'pbt-security-'),
    'static': ('security', 'pbt-static-'), 'soak': ('soak', 'pbt-soak-'),
}
SHA = re.compile(r'[0-9a-f]{40}\Z')


class CollectError(ValueError):
    pass


def gh_json(path):
    return json.loads(subprocess.run(['gh', 'api', path], check=True, capture_output=True, timeout=120).stdout)


def gh_bytes(path):
    return subprocess.run(['gh', 'api', path], check=True, capture_output=True, timeout=600).stdout


def provider_digest(artifact):
    digest = artifact.get('digest') or ''
    if artifact.get('expired') is not False or not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
        raise CollectError(f"artifact_without_provider_digest_{artifact.get('name')}")
    return digest.split(':', 1)[1]


def collect(repo, kind, head, base, pr, out, policy, api=gh_json, download=gh_bytes):
    if not (SHA.fullmatch(head) and SHA.fullmatch(base)):
        raise CollectError('expected_sha_format')
    rules = policy['targets'].get(kind)
    if rules is None:
        raise CollectError('unsupported_target_event')
    runs = api(f'repos/{repo}/actions/runs?head_sha={head}&per_page=100')['workflow_runs']
    chosen = {}
    for run in sorted(runs, key=lambda r: (r['created_at'], r['run_attempt'])):
        role = WORKFLOW_ROLE.get(run['name'])
        if role and run['event'] in rules['run_events'] and run['head_sha'] == head:
            chosen[role] = run   # Latest wins, whatever its conclusion: a later failure is not hidden.
    manifest_runs = {role: {'id': r['id'], 'head_sha': r['head_sha'], 'event': r['event'], 'status': r['status'],
                            'conclusion': r['conclusion'], 'attempt': r['run_attempt']} for role, r in chosen.items()}
    artifacts = {}
    out.mkdir(parents=True, exist_ok=True)
    for role in rules['roles']:
        workflow, prefix = ARTIFACT_PREFIX[role]
        if workflow not in chosen:
            raise CollectError(f'missing_workflow_run_{workflow}')
        run_id = chosen[workflow]['id']
        listed = api(f'repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100')['artifacts']
        matches = [a for a in listed if a['name'].startswith(prefix)]
        if len(matches) != 1:
            raise CollectError(f'artifact_not_unique_{role}')
        artifact = matches[0]
        expected = provider_digest(artifact)
        raw = download(f"repos/{repo}/actions/artifacts/{artifact['id']}/zip")
        if hashlib.sha256(raw).hexdigest() != expected:
            raise CollectError(f'provider_digest_mismatch_{role}')
        # Refetch after download: a digest stale by the time the bytes arrived is not evidence.
        again = api(f"repos/{repo}/actions/artifacts/{artifact['id']}")
        if provider_digest(again) != expected:
            raise CollectError(f'provider_digest_changed_{role}')
        (out / f'{role}.zip').write_bytes(raw)
        artifacts[role] = {'id': artifact['id'], 'run_id': run_id, 'filename': f'{role}.zip', 'sha256': expected}
    target = {'kind': kind, 'pr_number': pr, 'ref': f'refs/pull/{pr}/head' if kind == 'pull_request' else policy['main_ref']}
    manifest = {'schema': 'pbt-exact-head-evidence-matrix-v2', 'repository': repo, 'head_sha': head, 'base_sha': base,
                'target': target, 'runs': manifest_runs, 'artifacts': artifacts}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    return manifest


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', default='neuron7x/pbt-site')
    p.add_argument('--kind', required=True, choices=('pull_request', 'push', 'workflow_dispatch'))
    p.add_argument('--head', required=True)
    p.add_argument('--base', required=True)
    p.add_argument('--pr', type=int, default=None)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--policy', type=Path, default=Path(__file__).resolve().parent.parent / 'config/evidence-policy.json')
    a = p.parse_args(argv)
    try:
        collect(a.repo, a.kind, a.head, a.base, a.pr, a.out, json.loads(a.policy.read_text(encoding='utf-8')))
    except (CollectError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'FAIL', 'reason': str(exc)[:150], 'error_type': type(exc).__name__}))
        return 1
    print(json.dumps({'status': 'COLLECTED', 'head_sha': a.head, 'out': str(a.out)}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
