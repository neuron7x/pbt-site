"""Recovery files stay owner-only while being written and after interrupted restores."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
RESTORE = ROOT / 'ops/restore.py'
DRIVER = r'''
import importlib.util, json, os, signal, sys
from pathlib import Path
script, folder, mode, mask = sys.argv[1:]
work = Path(folder)
spec = importlib.util.spec_from_file_location('restore_permission_probe', script)
restore = importlib.util.module_from_spec(spec); spec.loader.exec_module(restore)
os.umask(int(mask))
observed = {'candidate_modes': [], 'copy_modes': []}
publish, fsync = restore._publish, restore.os.fsync
def inspect_publish(tmp, dst):
    assert tmp.stat().st_size > 0
    observed['candidate_modes'].append(tmp.stat().st_mode & 0o777)
    if mode == 'kill_candidate':
        os.kill(os.getpid(), signal.SIGKILL)
    return publish(tmp, dst)
def inspect_fsync(fd):
    for part in work.glob('*.part'):
        assert part.stat().st_size > 0
        observed['copy_modes'].append(part.stat().st_mode & 0o777)
        if mode == 'kill_copy':
            os.kill(os.getpid(), signal.SIGKILL)
    return fsync(fd)
restore._publish, restore.os.fsync = inspect_publish, inspect_fsync
code = restore.main([str(work / 'snapshot.db'), '--db', str(work / 'leads.db'),
                     '--log', str(work / 'absent.log'), '--min-seq', '1', '--port', '1'])
print(json.dumps(observed))
sys.exit(code)
'''


def _database(path, payload):
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE leads(id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT)')
        db.execute('INSERT INTO leads(payload) VALUES(?)', (payload,))


def _setup(tmp):
    _database(tmp / 'snapshot.db', 'snapshot fixture')
    _database(tmp / 'leads.db', 'old fixture')


def _run(tmp, mode='inspect', mask=0):
    return subprocess.run([sys.executable, '-c', DRIVER, str(RESTORE), str(tmp), mode, str(mask)],
                          capture_output=True, text=True, timeout=15)


@pytest.mark.parametrize('mask', [0, 0o022])
def test_restore_staging_is_private_before_publish_or_evidence_sync(tmp_path, mask):
    _setup(tmp_path)
    source_before = (tmp_path / 'snapshot.db').read_bytes()

    run = _run(tmp_path, mask=mask)

    assert run.returncode == 0, run.stdout + run.stderr
    observed = json.loads(run.stdout.splitlines()[-1])
    assert observed['candidate_modes'] == [0o600]
    assert observed['copy_modes'] and set(observed['copy_modes']) == {0o600}
    assert (tmp_path / 'leads.db').stat().st_mode & 0o777 == 0o600
    assert (tmp_path / 'snapshot.db').read_bytes() == source_before


@pytest.mark.parametrize('mode', ['kill_candidate', 'kill_copy'])
def test_interrupted_restore_leaves_only_private_recovery_residue(tmp_path, mode):
    _setup(tmp_path)
    original = (tmp_path / 'leads.db').read_bytes()

    run = _run(tmp_path, mode)

    assert run.returncode == -9, run.stdout + run.stderr
    residue = [*tmp_path.glob('*.restore-tmp'), *tmp_path.glob('*.part')]
    assert residue and all(path.stat().st_size > 0 for path in residue)
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in residue)
    assert (tmp_path / 'leads.db').read_bytes() == original


def test_restore_removes_a_stale_temp_symlink_without_touching_its_target(tmp_path):
    _setup(tmp_path)
    victim = tmp_path / 'unrelated.txt'
    victim.write_bytes(b'untouched fixture')
    (tmp_path / 'leads.db.restore-tmp').symlink_to(victim)

    run = _run(tmp_path)

    assert run.returncode == 0, run.stdout + run.stderr
    assert victim.read_bytes() == b'untouched fixture'
    with sqlite3.connect(tmp_path / 'leads.db') as db:
        assert db.execute('SELECT payload FROM leads').fetchone() == ('snapshot fixture',)


@pytest.mark.parametrize('kind', ['file', 'symlink'])
def test_preservation_copy_refuses_an_existing_staging_path(tmp_path, kind):
    spec = importlib.util.spec_from_file_location('restore_copy_probe', RESTORE)
    restore = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(restore)
    source, destination = tmp_path / 'source', tmp_path / 'preserved'
    source.write_bytes(b'source fixture')
    destination.write_bytes(b'previous preserved fixture')
    victim = tmp_path / 'unrelated'
    victim.write_bytes(b'untouched fixture')
    part = Path(str(destination) + '.part')
    if kind == 'symlink':
        part.symlink_to(victim)
    else:
        part.write_bytes(b'previous staging fixture')
    before = part.read_bytes()

    with pytest.raises(FileExistsError):
        restore._durable_copy(source, destination)

    assert part.read_bytes() == before
    assert victim.read_bytes() == b'untouched fixture'
    assert source.read_bytes() == b'source fixture'
    assert destination.read_bytes() == b'previous preserved fixture'


@pytest.mark.parametrize('suffix', ['.restore-tmp', '.pre-restore-20000101-000000.part'])
@pytest.mark.parametrize('alias', [False, True])
def test_restore_never_cleans_its_selected_backup_input(tmp_path, suffix, alias):
    destination = tmp_path / 'leads.db'
    _database(destination, 'old fixture')
    source = Path(str(destination) + suffix)
    _database(source, 'selected snapshot fixture')
    selected = source
    if alias:
        selected = tmp_path / 'selected.db'
        selected.symlink_to(source)
    unrelated = tmp_path / 'leads.db.pre-restore-stale.part'
    unrelated.write_bytes(b'unrelated recovery fixture')
    original, snapshot = destination.read_bytes(), source.read_bytes()

    run = subprocess.run(
        [sys.executable, str(RESTORE), str(selected), '--db', str(destination),
         '--log', str(tmp_path / 'none.log'), '--min-seq', '1', '--port', '1'],
        capture_output=True, text=True, timeout=5,
    )

    assert run.returncode == 1 and 'backup path conflicts with restore staging' in run.stderr
    assert source.read_bytes() == snapshot and selected.exists()
    assert destination.read_bytes() == original
    assert unrelated.read_bytes() == b'unrelated recovery fixture'
    assert not Path(str(destination) + '.server-lock').exists(), 'refusal must precede writes'


@pytest.mark.parametrize(('name', 'neighbor_name'), [
    pytest.param('leads[1].db', 'leads1.db', id='brackets'),
    pytest.param('leads*.db', 'leads-other.db', id='star'),
    pytest.param('leads?.db', 'leadsA.db', id='question'),
])
def test_restore_staging_cleanup_uses_literal_destination_name(tmp_path, name, neighbor_name):
    source, destination = tmp_path / 'snapshot.db', tmp_path / name
    _database(source, 'selected snapshot fixture')
    _database(destination, 'old fixture')
    source_before = source.read_bytes()
    own_staging = Path(str(destination) + '.pre-restore-stale.part')
    own_staging.write_bytes(b'owned interrupted copy fixture')
    unrelated = tmp_path / (neighbor_name + '.pre-restore-stale.part')
    unrelated.write_bytes(b'unrelated recovery fixture')

    run = subprocess.run(
        [sys.executable, str(RESTORE), str(source), '--db', str(destination),
         '--log', str(tmp_path / 'none.log'), '--min-seq', '1', '--port', '1'],
        capture_output=True, text=True, timeout=5,
    )

    assert run.returncode == 0, run.stdout + run.stderr
    assert unrelated.exists(), 'cleanup removed another database recovery file'
    assert unrelated.read_bytes() == b'unrelated recovery fixture'
    assert not own_staging.exists()
    assert source.read_bytes() == source_before
    assert destination.stat().st_mode & 0o777 == 0o600
    with sqlite3.connect(destination) as db:
        assert db.execute('SELECT payload FROM leads').fetchone() == ('selected snapshot fixture',)


@pytest.mark.parametrize('name', ['leads[1].db', 'leads*.db', 'leads?.db'],
                         ids=['brackets', 'star', 'question'])
@pytest.mark.parametrize('alias', [False, True], ids=['direct', 'symlink'])
def test_literal_destination_still_refuses_its_selected_staging_input(tmp_path, name, alias):
    destination = tmp_path / name
    _database(destination, 'old fixture')
    source = Path(str(destination) + '.pre-restore-selected.part')
    _database(source, 'selected snapshot fixture')
    selected = source
    if alias:
        selected = tmp_path / 'selected.db'
        selected.symlink_to(source)
    original, snapshot = destination.read_bytes(), source.read_bytes()

    run = subprocess.run(
        [sys.executable, str(RESTORE), str(selected), '--db', str(destination),
         '--log', str(tmp_path / 'none.log'), '--min-seq', '1', '--port', '1'],
        capture_output=True, text=True, timeout=5,
    )

    assert run.returncode == 1 and 'backup path conflicts with restore staging' in run.stderr
    assert source.read_bytes() == snapshot and selected.exists()
    assert destination.read_bytes() == original
    assert not Path(str(destination) + '.server-lock').exists(), 'refusal must precede writes'
