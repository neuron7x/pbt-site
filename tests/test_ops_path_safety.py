"""Backup retention never owns its source; restore uses the literal selected path."""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _database(path, label):
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE leads(id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT)')
        db.execute('INSERT INTO leads(payload) VALUES(?)', (label,))


def _backup(source, directory):
    return subprocess.run(
        [sys.executable, str(ROOT / 'ops/backup.py')],
        env={**os.environ, 'LEAD_DB': str(source), 'BACKUP_DIR': str(directory), 'BACKUP_KEEP': '1'},
        capture_output=True, text=True, timeout=15,
    )


@pytest.mark.parametrize('name', ['leads-20000101-000000.db', 'leads-interrupted.tmp', 'live.db'])
def test_backup_refuses_source_in_retention_directory_before_any_mutation(tmp_path, name):
    directory = tmp_path / 'backups'
    directory.mkdir(mode=0o750)
    source = directory / name
    _database(source, 'accepted fixture')
    (directory / 'leads-old.tmp').write_bytes(b'interrupted fixture')
    (directory / 'leads-19990101-000000.db').write_bytes(b'previous fixture')
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    mode = directory.stat().st_mode

    run = _backup(source, directory)

    assert run.returncode == 1 and 'backup FAIL' in run.stderr
    assert 'backup OK' not in run.stdout
    assert directory.stat().st_mode == mode, 'refusal must precede chmod'
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == before


@pytest.mark.parametrize('alias', ['backup_directory', 'source_target', 'source_name'])
def test_backup_path_aliases_cannot_enter_retention_or_cleanup(tmp_path, alias):
    directory = tmp_path / 'backups'
    directory.mkdir(mode=0o750)
    if alias == 'source_name':
        actual = tmp_path / 'accepted.db'
        source = directory / 'leads-20000101-000000.db'
        _database(actual, 'accepted fixture')
        source.symlink_to(actual)
    else:
        actual = directory / 'leads-20000101-000000.db'
        _database(actual, 'accepted fixture')
        source = actual
        if alias == 'source_target':
            source = tmp_path / 'selected.db'
            source.symlink_to(actual)
    selected_directory = directory
    if alias == 'backup_directory':
        selected_directory = tmp_path / 'backup-alias'
        selected_directory.symlink_to(directory, target_is_directory=True)
    before, mode = actual.read_bytes(), directory.stat().st_mode
    entries = {p.name for p in directory.iterdir()}

    run = _backup(source, selected_directory)

    assert run.returncode == 1 and 'backup FAIL' in run.stderr
    assert source.exists() and actual.read_bytes() == before
    assert directory.stat().st_mode == mode
    assert {p.name for p in directory.iterdir()} == entries


def test_backup_accepts_a_snapshot_named_source_outside_retention(tmp_path):
    source = tmp_path / 'leads-20000101-000000.db'
    _database(source, 'accepted fixture')
    before = source.read_bytes()
    directory = tmp_path / 'backups'

    run = _backup(source, directory)

    assert run.returncode == 0, run.stderr
    assert source.read_bytes() == before
    snapshots = list(directory.glob('leads-*.db'))
    assert len(snapshots) == 1
    with sqlite3.connect(snapshots[0]) as db:
        assert db.execute('SELECT payload FROM leads').fetchone() == ('accepted fixture',)


@pytest.mark.parametrize('suffix', ['#chosen', '?chosen', '%23chosen', '%3Fchosen'])
def test_restore_reads_literal_uri_metacharacters_without_substituting_a_neighbor(tmp_path, suffix):
    source = tmp_path / ('snapshot.db' + suffix)
    neighbor = tmp_path / 'snapshot.db'
    _database(source, 'selected fixture')
    _database(neighbor, 'wrong neighboring fixture')
    source_before, neighbor_before = source.read_bytes(), neighbor.read_bytes()
    target = tmp_path / 'restored.db'

    run = subprocess.run(
        [sys.executable, str(ROOT / 'ops/restore.py'), str(source), '--db', str(target),
         '--log', str(tmp_path / 'absent.log'), '--min-seq', '1', '--port', '1'],
        capture_output=True, text=True, timeout=15,
    )

    assert run.returncode == 0, run.stderr
    with sqlite3.connect(target) as db:
        assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert db.execute('SELECT payload FROM leads').fetchone() == ('selected fixture',)
    assert source.read_bytes() == source_before
    assert neighbor.read_bytes() == neighbor_before
