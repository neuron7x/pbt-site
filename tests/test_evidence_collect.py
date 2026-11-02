"""EVD-06: the collector binds bytes to the provider's digest, with a stubbed authenticated API."""
import copy
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
                              'conclusion': 'success', 'run_attempt': 1, 'created_at': '2026-11-01T00:00:00Z',
                              'run_started_at': '2026-11-01T00:00:00Z', 'pull_requests': [{'number': 14}]})
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
        if '/jobs?' in path:
            return {'jobs': [{'name': 'j', 'id': 7, 'status': 'completed', 'conclusion': 'success'}]}
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
    assert m['schema'] == 'pbt-exact-head-evidence-matrix-v2' and len(m['artifacts']) == 10
    assert (tmp_path / 'manifest.json').exists() and all(r['pull_requests'] == [14] for r in m['runs'].values())
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
    p.runs.append({**p.runs[0], 'id': 999, 'run_attempt': 2, 'conclusion': 'failure', 'created_at': '2026-11-02T00:00:00Z', 'run_started_at': '2026-11-02T00:00:00Z'})
    for a in p.artifacts.values():
        if a['run'] == p.runs[0]['id']:
            a['run'] = 999
            a['name'] = a['name'].rsplit('-', 2)[0] + '-999-2'
    m = _collect(p, tmp_path)
    role = ec.WORKFLOW_ROLE[p.runs[0]['name']]
    assert m['runs'][role]['conclusion'] == 'failure'  # The offline verifier will reject it.


def test_older_created_failed_rerun_not_hidden_by_newer_created_success(tmp_path):
    p = Provider()
    old = p.runs[0]
    old.update(run_attempt=2, run_started_at='2026-11-02T12:30:00Z', conclusion='failure')
    p.runs.append({**old, 'id': 999, 'created_at': '2026-11-02T11:00:00Z',
                   'run_started_at': '2026-11-02T11:00:00Z',
                   'run_attempt': 1, 'conclusion': 'success'})
    for artifact in p.artifacts.values():
        if artifact['run'] == old['id']:
            artifact['name'] = artifact['name'].rsplit('-', 1)[0] + '-2'
    m = _collect(p, tmp_path)
    role = ec.WORKFLOW_ROLE[old['name']]
    assert m['runs'][role]['id'] == old['id']
    assert m['runs'][role]['attempt'] == 2
    assert m['runs'][role]['conclusion'] == 'failure'


def test_successful_rerun_ignores_earlier_attempt_archives(tmp_path):
    p = Provider()
    run = p.runs[0]
    run.update(run_attempt=2, run_started_at='2026-11-02T12:30:00Z')
    for aid, artifact in list(p.artifacts.items()):
        if artifact['run'] != run['id']:
            continue
        new_id = aid + 1000
        raw = p.bytes[aid] + b'-attempt-2'
        p.bytes[new_id] = raw
        p.artifacts[new_id] = {
            **artifact, 'id': new_id,
            'name': artifact['name'].rsplit('-', 1)[0] + '-2',
            'digest': 'sha256:' + hashlib.sha256(raw).hexdigest(),
        }
    m = _collect(p, tmp_path)
    for role, (owner, prefix) in ec.ARTIFACT_PREFIX.items():
        if owner == 'full':
            expected_name = f"{prefix}{run['id']}-2"
            expected_id = next(a['id'] for a in p.artifacts.values() if a['name'] == expected_name)
            assert m['artifacts'][role]['id'] == expected_id


def test_rerun_missing_latest_attempt_archive_fails_closed(tmp_path):
    p = Provider()
    p.runs[0].update(run_attempt=2, run_started_at='2026-11-02T12:30:00Z')
    with pytest.raises(ec.CollectError, match='artifact_not_unique_release'):
        _collect(p, tmp_path)


def test_truncated_artifact_listing_fails_closed(tmp_path):
    p = Provider()
    original = p.api

    def truncated(path):
        response = original(path)
        if path.endswith('/artifacts?per_page=100'):
            return {**response, 'total_count': len(response['artifacts']) + 1}
        return response

    p.api = truncated
    with pytest.raises(ec.CollectError, match='artifact_listing_truncated_release'):
        _collect(p, tmp_path)


def test_newer_pending_attempt_invalidates_old_manifest(tmp_path):
    p = Provider()
    _collect(p, tmp_path)
    p.runs.append({**p.runs[0], 'id': 999, 'status': 'in_progress',
                   'conclusion': None, 'run_attempt': 2,
                   'run_started_at': '2026-11-02T12:30:00Z'})
    with pytest.raises(ec.CollectError, match='incomplete_workflow_runs_full'):
        _collect(p, tmp_path)
    assert not (tmp_path / 'manifest.json').exists()


def test_same_second_different_runs_are_not_arbitrarily_ordered(tmp_path):
    p = Provider()
    older = p.runs[0]
    older.update(run_started_at='2026-11-02T12:00:00Z', run_attempt=2)
    p.runs.append({**older, 'id': 999, 'created_at': '2026-11-02T12:00:00Z',
                   'run_started_at': '2026-11-02T12:00:00Z',
                   'run_attempt': 1, 'conclusion': 'failure'})
    with pytest.raises(ec.CollectError, match='ambiguous_attempt_order_full'):
        _collect(p, tmp_path)


def test_missing_attempt_started_at_fails_closed(tmp_path):
    p = Provider()
    p.runs[0].pop('run_started_at')
    with pytest.raises(ec.CollectError, match='run_attempt_started_at_missing_or_invalid'):
        _collect(p, tmp_path)


def test_truncated_run_list_fails_closed(tmp_path):
    p = Provider()
    old_api = p.api

    def truncated(path):
        result = old_api(path)
        if '/actions/runs?' in path:
            return {**result, 'total_count': len(p.runs) + 1}
        return result

    p.api = truncated
    with pytest.raises(ec.CollectError, match='workflow_run_listing_truncated'):
        _collect(p, tmp_path)


def test_closure_watcher_is_base_checkout_compatible_and_attempt_ordered():
    # A PR editing this YAML runs the workflow from the PR, but checks out BASE main.
    # Do not import a NEW helper absent on that measured base: prove the embedded code compiles.
    import textwrap
    source = (Path(__file__).resolve().parents[1] / '.github/workflows/evidence-closure.yml').read_text()
    marker = '      - name: Wait boundedly for all five exact-main push workflows'
    script = source.split(marker, 1)[1].split("          python - <<'PY'\\n", 1)
    if len(script) == 1:
        script = source.split(marker, 1)[1].split("          python - <<'PY'\n", 1)
    assert len(script) == 2
    code = textwrap.dedent(script[1].split("          PY\n", 1)[0])
    compile(code, 'pbt-evidence-closure-inline', 'exec')
    assert 'from tools.evidence_collect import WORKFLOW_ROLE\n' in code
    assert 'run.get(\'run_started_at\')' in code
    assert 'and not pending' in code
    assert 'AMBIGUOUS_ATTEMPT_ORDER_' in code
    assert 'select_runs' not in code
    assert "key=lambda r: (r['created_at'], r['run_attempt'])" not in code


def test_stable_run_snapshot_is_refetched_at_publication(tmp_path):
    p = Provider()
    original = p.api
    calls = []

    def observed(path):
        if '/actions/runs?' in path:
            calls.append(path)
        return original(path)

    p.api = observed
    manifest = _collect(p, tmp_path)
    assert len(calls) == 2  # initial discovery and final publication barrier
    assert manifest['runs']['full']['conclusion'] == 'success'
    assert (tmp_path / 'manifest.json').is_file()


@pytest.mark.parametrize('status,conclusion', [
    ('in_progress', None), ('completed', 'failure'), ('completed', 'cancelled'),
])
def test_rerun_after_initial_listing_cannot_publish_stale_success(tmp_path, status, conclusion):
    p = Provider()
    original = p.api
    seen = 0

    def transition(path):
        nonlocal seen
        result = original(path)
        if '/actions/runs?' in path:
            seen += 1
            if seen == 1:
                # The old attempt's ZIPs remain authentic and downloadable.
                # Only the provider's live run attempt moves AFTER the first GET.
                initial = copy.deepcopy(result)
                p.runs[0] = {
                    **p.runs[0], 'run_attempt': 2,
                    'run_started_at': '2026-11-02T12:30:00Z',
                    'status': status, 'conclusion': conclusion,
                }
                return initial
        return result

    p.api = transition
    with pytest.raises(ec.CollectError, match='run_snapshot_drift'):
        _collect(p, tmp_path)
    assert seen == 2
    assert not (tmp_path / 'manifest.json').exists()


def test_newer_required_role_after_listing_blocks_old_manifest(tmp_path):
    p = Provider()
    original = p.api
    seen = 0

    def transition(path):
        nonlocal seen
        result = original(path)
        if '/actions/runs?' in path:
            seen += 1
            if seen == 1:
                initial = copy.deepcopy(result)
                p.runs.append({
                    **p.runs[0], 'id': 999, 'run_attempt': 1,
                    'created_at': '2026-11-02T13:00:00Z',
                    'run_started_at': '2026-11-02T13:00:00Z',
                    'status': 'completed', 'conclusion': 'failure',
                })
                return initial
        return result

    p.api = transition
    with pytest.raises(ec.CollectError, match='run_snapshot_drift'):
        _collect(p, tmp_path)
    assert seen == 2
    assert not (tmp_path / 'manifest.json').exists()


def test_truncated_final_listing_is_not_publishable(tmp_path):
    p = Provider()
    original = p.api
    seen = 0

    def truncated(path):
        nonlocal seen
        result = original(path)
        if '/actions/runs?' in path:
            seen += 1
            if seen == 2:
                return {**result, 'total_count': len(result['workflow_runs']) + 1}
        return result

    p.api = truncated
    with pytest.raises(ec.CollectError, match='run_snapshot_drift_listing_truncated'):
        _collect(p, tmp_path)
    assert not (tmp_path / 'manifest.json').exists()


def test_inflight_rerun_does_not_overwrite_previously_verified_archives(tmp_path):
    p = Provider()
    _collect(p, tmp_path)
    original_bytes = {
        role: (tmp_path / f'{role}.zip').read_bytes()
        for role in POLICY['targets']['pull_request']['roles']
    }
    original = p.api
    seen = 0

    def transition(path):
        nonlocal seen
        result = original(path)
        if '/actions/runs?' in path:
            seen += 1
            if seen == 1:
                initial = copy.deepcopy(result)
                p.runs[0] = {**p.runs[0], 'status': 'in_progress',
                             'conclusion': None, 'run_attempt': 2,
                             'run_started_at': '2026-11-02T12:30:00Z'}
                return initial
        return result

    p.api = transition
    with pytest.raises(ec.CollectError, match='run_snapshot_drift'):
        _collect(p, tmp_path)
    assert not (tmp_path / 'manifest.json').exists()
    assert all(
        (tmp_path / f'{role}.zip').read_bytes() == original_bytes[role]
        for role in original_bytes
    )


def test_failed_refresh_invalidates_previously_successful_manifest(tmp_path):
    _collect(Provider(), tmp_path)
    assert (tmp_path / 'manifest.json').exists()
    broken = Provider()
    broken.bytes[101] += b'-corrupted'
    with pytest.raises(ec.CollectError, match='provider_digest_mismatch'):
        _collect(broken, tmp_path)
    assert not (tmp_path / 'manifest.json').exists(), 'stale evidence must not survive an unsuccessful refresh'


def test_failed_refresh_keeps_archives_unmodified_until_complete(tmp_path):
    _collect(Provider(), tmp_path)
    before = {role: (tmp_path / f'{role}.zip').read_bytes()
              for role in POLICY['targets']['pull_request']['roles']}
    broken = Provider()
    broken.bytes[100] = b'valid-new-release'
    broken.artifacts[100]['digest'] = 'sha256:' + hashlib.sha256(broken.bytes[100]).hexdigest()
    broken.bytes[101] += b'-bad-baseline'
    with pytest.raises(ec.CollectError, match='provider_digest_mismatch'):
        _collect(broken, tmp_path)
    assert not (tmp_path / 'manifest.json').exists()
    assert all((tmp_path / f'{role}.zip').read_bytes() == previous for role, previous in before.items())


def test_successful_refresh_publishes_complete_new_manifest(tmp_path):
    _collect(Provider(), tmp_path)
    fresh = Provider()
    for aid, artifact in fresh.artifacts.items():
        fresh.bytes[aid] = f'refreshed-{aid}'.encode()
        artifact['digest'] = 'sha256:' + hashlib.sha256(fresh.bytes[aid]).hexdigest()
    manifest = _collect(fresh, tmp_path)
    assert json.loads((tmp_path / 'manifest.json').read_text()) == manifest
    for role, item in manifest['artifacts'].items():
        assert hashlib.sha256((tmp_path / f'{role}.zip').read_bytes()).hexdigest() == item['sha256']


def test_missing_current_workflow_invalidates_old_manifest(tmp_path):
    _collect(Provider(), tmp_path)
    partial = Provider()
    partial.runs = [run for run in partial.runs if ec.WORKFLOW_ROLE[run['name']] != 'soak']
    with pytest.raises(ec.CollectError, match='missing_workflow_run_soak'):
        _collect(partial, tmp_path)
    assert not (tmp_path / 'manifest.json').exists()
