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
import os
from pathlib import Path
from tempfile import TemporaryDirectory
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
    'mutation': ('full', 'pbt-mutation-'), 'sast': ('security', 'pbt-sast-'),
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
    # A new collection attempt invalidates any earlier successful receipt immediately.
    # A failed refetch must never leave a previously accepted manifest publishable.
    out.mkdir(parents=True, exist_ok=True)
    (out / 'manifest.json').unlink(missing_ok=True)
    runs = api(f'repos/{repo}/actions/runs?head_sha={head}&per_page=100')['workflow_runs']
    chosen = {}
    for run in sorted(runs, key=lambda r: (r['created_at'], r['run_attempt'])):
        role = WORKFLOW_ROLE.get(run['name'])
        if role and run['event'] in rules['run_events'] and run['head_sha'] == head:
            chosen[role] = run   # Latest wins, whatever its conclusion: a later failure is not hidden.
    manifest_runs = {role: {'id': r['id'], 'head_sha': r['head_sha'], 'event': r['event'], 'status': r['status'],
                            'conclusion': r['conclusion'], 'attempt': r['run_attempt'],
                            'pull_requests': [x['number'] for x in r.get('pull_requests') or []]} for role, r in chosen.items()}
    for role, record in manifest_runs.items():
        listed = api(f"repos/{repo}/actions/runs/{record['id']}/attempts/{record['attempt']}/jobs?per_page=100")['jobs']
        record['jobs'] = {j['name']: {'id': j['id'], 'status': j['status'], 'conclusion': j['conclusion']} for j in listed}
    artifacts = {}
    downloaded = {}
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
        downloaded[role] = raw
        artifacts[role] = {'id': artifact['id'], 'run_id': run_id, 'filename': f'{role}.zip', 'sha256': expected}
    target = {'kind': kind, 'pr_number': pr, 'ref': f'refs/pull/{pr}/head' if kind == 'pull_request' else policy['main_ref']}
    manifest = {'schema': 'pbt-exact-head-evidence-matrix-v2', 'repository': repo, 'head_sha': head, 'base_sha': base,
                'target': target, 'runs': manifest_runs, 'artifacts': artifacts}
    # Stage the complete byte set first; the manifest is the final commit marker.
    # On error, TemporaryDirectory removes staged bytes and no manifest can be accepted.
    with TemporaryDirectory(prefix='.pbt-evidence-stage-', dir=out) as staging:
        stage = Path(staging)
        for role in rules['roles']:
            (stage / f'{role}.zip').write_bytes(downloaded[role])
        (stage / 'manifest.json').write_text(
            json.dumps(manifest, indent=1, sort_keys=True) + '\n', encoding='utf-8')
        for role in rules['roles']:
            os.replace(stage / f'{role}.zip', out / f'{role}.zip')
        os.replace(stage / 'manifest.json', out / 'manifest.json')
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
