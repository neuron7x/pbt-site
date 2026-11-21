"""A clean AST result must describe the exact committed source bytes."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def source_tree(tmp_path):
    root = tmp_path / 'source'
    (root / 'tools').mkdir(parents=True)
    shutil.copy2(ROOT / 'tools/security_static.py', root / 'tools/security_static.py')
    for directory in ('server', 'ops'):
        (root / directory).mkdir()
        for index in range(3):
            (root / directory / f'module{index}.py').write_text('VALUE = 1\n')
    for args in (['init', '-q'], ['add', '-A'],
                 ['-c', 'user.name=fixture', '-c', 'user.email=fixture@invalid',
                  'commit', '-qm', 'synthetic source']):
        subprocess.run(['git', *args], cwd=root, check=True, capture_output=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    return root, head


def scan(root, head):
    out = root / 'report.json'
    run = subprocess.run(
        [sys.executable, str(root / 'tools/security_static.py'),
         '--expected-head', head, '--output', str(out)],
        cwd=root, text=True, capture_output=True, timeout=15, check=False)
    return run, json.loads(out.read_text())


def test_clean_source_records_every_scanned_blob(source_tree):
    root, head = source_tree
    run, report = scan(root, head)
    assert run.returncode == 0 and report['status'] == 'PASS', run.stderr
    assert report['files_scanned'] == 6
    records = report['source_files']
    assert len(records) == 6 and len({item['path'] for item in records}) == 6
    for item in records:
        raw = (root / item['path']).read_bytes()
        expected = subprocess.check_output(
            ['git', 'rev-parse', f"{head}:{item['path']}"], cwd=root, text=True).strip()
        assert item['git_blob_sha'] == expected
        assert item['sha256'] == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize('change', ['edit', 'delete', 'untracked', 'symlink', 'hidden_edit'])
def test_worktree_drift_never_gets_a_clean_source_receipt(source_tree, change):
    root, head = source_tree
    path = root / 'server/module0.py'
    if change == 'delete':
        path.unlink()
    elif change == 'untracked':
        (root / 'server/extra.py').write_text('VALUE = 2\n')
    elif change == 'symlink':
        path.unlink()
        path.symlink_to(root / 'ops/module0.py')
    else:
        if change == 'hidden_edit':
            subprocess.run(['git', 'update-index', '--assume-unchanged', 'server/module0.py'],
                           cwd=root, check=True, capture_output=True)
        path.write_text('VALUE = 2\n')
    run, report = scan(root, head)
    assert run.returncode == 1, report
    assert report['status'] == 'FAIL' and report['findings']
    assert 'VALUE = 2' not in run.stdout + run.stderr + json.dumps(report)


def test_removing_committed_unsafe_code_cannot_certify_its_old_sha(source_tree):
    root, _ = source_tree
    path = root / 'server/module0.py'
    path.write_text("eval('1 + 1')\n")
    subprocess.run(['git', 'add', 'server/module0.py'], cwd=root, check=True)
    subprocess.run(['git', '-c', 'user.name=fixture', '-c', 'user.email=fixture@invalid',
                    'commit', '-qm', 'synthetic forbidden primitive'], cwd=root, check=True,
                   capture_output=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    assert scan(root, head)[1]['status'] == 'FAIL'
    path.write_text('VALUE = 1\n')
    run, report = scan(root, head)
    assert run.returncode == 1 and report['status'] == 'FAIL', report


def test_unrelated_generated_output_does_not_change_source_identity(source_tree):
    root, head = source_tree
    (root / 'artifacts').mkdir()
    (root / 'artifacts/unrelated.txt').write_text('synthetic output\n')
    run, report = scan(root, head)
    assert run.returncode == 0 and report['status'] == 'PASS'


@pytest.mark.parametrize('tracked', [False, True])
def test_directory_symlinks_cannot_hide_imported_python(source_tree, tracked):
    root, _ = source_tree
    (root / 'outside').mkdir()
    (root / 'outside/hidden.py').write_text("eval('1 + 1')\n")
    (root / 'server/linked').symlink_to('../outside', target_is_directory=True)
    (root / 'server/module0.py').write_text('from .linked import hidden\n')
    paths = ['server/module0.py'] + (['server/linked'] if tracked else [])
    subprocess.run(['git', 'add', *paths], cwd=root, check=True, capture_output=True)
    subprocess.run(['git', '-c', 'user.name=fixture', '-c', 'user.email=fixture@invalid',
                    'commit', '-qm', 'synthetic directory alias'], cwd=root, check=True,
                   capture_output=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    run, report = scan(root, head)
    assert run.returncode == 1 and report['status'] == 'FAIL', report


def test_git_replacement_cannot_relabel_safe_bytes_as_an_unsafe_commit(source_tree):
    root, _ = source_tree
    path = root / 'server/module0.py'
    heads = []
    for content in ("eval('1 + 1')\n", 'VALUE = 1\n'):
        path.write_text(content)
        subprocess.run(['git', 'add', 'server/module0.py'], cwd=root, check=True,
                       capture_output=True)
        subprocess.run(['git', '-c', 'user.name=fixture', '-c', 'user.email=fixture@invalid',
                        'commit', '-qm', 'synthetic replacement control'], cwd=root, check=True,
                       capture_output=True)
        heads.append(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root,
                                            text=True).strip())
    original, replacement = heads
    subprocess.run(['git', 'replace', original, replacement], cwd=root, check=True,
                   capture_output=True)
    subprocess.run(['git', 'reset', '--hard', original], cwd=root, check=True,
                   capture_output=True)
    assert path.read_text() == 'VALUE = 1\n'
    committed = subprocess.check_output(
        ['git', '--no-replace-objects', 'show', f'{original}:server/module0.py'],
        cwd=root, text=True)
    assert committed == "eval('1 + 1')\n"
    run, report = scan(root, original)
    assert run.returncode == 1 and report['status'] == 'FAIL', report
