"""EVD-06: the collector binds bytes to the provider's digest, with a stubbed authenticated API."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import evidence_collect as ec

HEAD, BASE = 'a' * 40, 'b' * 40
POLICY = json.loads((Path(__file__).resolve().parents[1] / 'config/evidence-policy.json').read_text())
NAMES = {v: k for k, v in ec.WORKFLOW_ROLE.items()}


class Provider:
    def __init__(self, event='pull_request'):
        self.bytes = {}
        self.artifacts = {}
        self.runs = []
        ids = {r: i + 1 for i, r in enumerate(NAMES)}
        for role, name in NAMES.items():
            self.runs.append({'id': ids[role], 'name': name, 'event': event, 'head_sha': HEAD, 'status': 'completed',
                              'conclusion': 'success', 'run_attempt': 1, 'created_at': '2026-11-01T00:00:00Z'})
        for i, (role, (workflow, prefix)) in enumerate(ec.ARTIFACT_PREFIX.items()):
            aid = 100 + i
            raw = f'zip-{role}'.encode()
            self.bytes[aid] = raw
            self.artifacts[aid] = {'id': aid, 'name': f'{prefix}{ids[workflow]}-1', 'expired': False,
                                   'digest': 'sha256:' + hashlib.sha256(raw).hexdigest(), 'run': ids[workflow]}
        self.calls = {}

    def api(self, path):
        if '/actions/runs?' in path:
            return {'workflow_runs': self.runs}
        if path.endswith('/artifacts?per_page=100'):
            run = int(path.split('/runs/')[1].split('/')[0])
            return {'artifacts': [a for a in self.artifacts.values() if a['run'] == run]}
        aid = int(path.rsplit('/', 1)[1])
        self.calls[aid] = self.calls.get(aid, 0) + 1
        return self.artifacts[aid]

    def download(self, path):
        return self.bytes[int(path.split('/artifacts/')[1].split('/')[0])]


def _collect(provider, tmp, kind='pull_request', pr=14):
    return ec.collect('o/r', kind, HEAD, BASE, pr, tmp, POLICY, provider.api, provider.download)


def test_positive_control_writes_provider_bound_manifest(tmp_path):
    m = _collect(Provider(), tmp_path)
    assert m['schema'] == 'pbt-exact-head-evidence-matrix-v2' and len(m['artifacts']) == 8
    assert (tmp_path / 'manifest.json').exists()
    for role, item in m['artifacts'].items():
        assert hashlib.sha256((tmp_path / f'{role}.zip').read_bytes()).hexdigest() == item['sha256']


def test_bytes_differing_from_provider_digest_are_rejected(tmp_path):
    p = Provider()
    p.bytes[100] += b'tampered in transit'
    with pytest.raises(ec.CollectError, match='provider_digest_mismatch'):
        _collect(p, tmp_path)


def test_artifact_replaced_during_download_is_rejected(tmp_path):
    p = Provider()
    real = p.api

    def swapping(path):
        result = real(path)
        if path.endswith('/100'):
            return {**result, 'digest': 'sha256:' + 'f' * 64}
        return result
    p.api = swapping
    with pytest.raises(ec.CollectError, match='provider_digest_changed'):
        _collect(p, tmp_path)


@pytest.mark.parametrize('mutate', [
    lambda a: a.update(digest=None), lambda a: a.update(expired=True), lambda a: a.update(digest='md5:00'),
])
def test_missing_expired_or_foreign_digest_is_rejected(tmp_path, mutate):
    p = Provider()
    mutate(p.artifacts[101])
    with pytest.raises(ec.CollectError, match='artifact_without_provider_digest'):
        _collect(p, tmp_path)


def test_pull_request_runs_are_not_collected_for_a_main_target(tmp_path):
    with pytest.raises(ec.CollectError, match='missing_workflow_run'):
        _collect(Provider('pull_request'), tmp_path, kind='push', pr=None)


def test_later_failed_attempt_is_not_hidden_by_an_earlier_success(tmp_path):
    p = Provider()
    p.runs.append({**p.runs[0], 'id': 999, 'run_attempt': 2, 'conclusion': 'failure', 'created_at': '2026-11-02T00:00:00Z'})
    for a in p.artifacts.values():
        if a['run'] == p.runs[0]['id']:
            a['run'] = 999
    m = _collect(p, tmp_path)
    role = ec.WORKFLOW_ROLE[p.runs[0]['name']]
    assert m['runs'][role]['conclusion'] == 'failure'  # The offline verifier will reject it.
