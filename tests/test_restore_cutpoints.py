"""DB-06: at every interruption of ops/restore.py a usable consistent database stays recoverable.

A driver wraps the unmodified script: every filesystem mutation it performs is counted, and
the Nth one dies by SIGKILL (before or after the operation) or fails with ENOSPC/EIO. The set
of cut indices is discovered from a clean run, so a new operation is automatically covered.
"""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
RESTORE = Path(os.environ.get('PBT_RESTORE_UNDER_TEST') or ROOT / 'ops' / 'restore.py')
DRIVER = r'''
import errno, json, os, runpy, signal, sys
mode, index, trace = sys.argv[1], int(sys.argv[2]), sys.argv[3]
script_args = sys.argv[4:]
count = [0]; names = []
def wrap(name):
    real = getattr(os, name)
    def wrapped(*a, **k):
        i = count[0]; count[0] += 1; names.append(name)
        if i == index and mode == 'kill_before':
            os.kill(os.getpid(), signal.SIGKILL)
        if i == index and mode in ('ENOSPC', 'EIO'):
            raise OSError(getattr(errno, mode), mode)
        try:
            return real(*a, **k)
        finally:  # A failing operation (unlink of an absent file) is still a reachable cutpoint.
            if i == index and mode == 'kill_after':
                os.kill(os.getpid(), signal.SIGKILL)
    setattr(os, name, wrapped)
for n in ('replace', 'rename', 'unlink', 'fsync', 'link'):
    wrap(n)
sys.argv = ['restore.py'] + script_args
code = 0
try:
    runpy.run_path(os.environ['RESTORE_SCRIPT'], run_name='__main__')
except SystemExit as e:
    code = e.code or 0
json.dump({'ops': names}, open(trace, 'w'))
sys.exit(code)
'''


def _make(path, ids):
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE leads(id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT, type TEXT, payload TEXT)')
        c.execute('''CREATE TABLE outbox(id INTEGER PRIMARY KEY AUTOINCREMENT,
                     lead_id INTEGER NOT NULL REFERENCES leads(id), channel TEXT NOT NULL)''')
        for i in ids:
            c.execute("INSERT INTO leads(id,created,type,payload) VALUES(?, '2026', 'rent', '{}')", (i,))
            c.execute("INSERT INTO outbox(lead_id,channel) VALUES(?, 'webhook')", (i,))


def _hot_journal(path):
    """Leave a genuine hot rollback journal: a writer died mid-transaction after spilling pages."""
    code = (f"import sqlite3,os,signal\nc=sqlite3.connect({str(path)!r},isolation_level=None)\n"
            "c.execute('PRAGMA cache_size=1')\nc.execute('BEGIN IMMEDIATE')\n"
            "c.execute(\"CREATE TABLE ghost(x)\")\n"
            "[c.execute('INSERT INTO ghost VALUES(?)',('g'*2000,)) for _ in range(200)]\n"
            "os.kill(os.getpid(),signal.SIGKILL)\n")
    assert subprocess.run([sys.executable, '-c', code]).returncode == -9
    assert Path(f'{path}-journal').exists()


def _run(tmp, mode, index, *extra):
    trace = tmp / 'trace.json'
    trace.unlink(missing_ok=True)
    args = [sys.executable, '-c', DRIVER, mode, str(index), str(trace),
            str(tmp / 'snapshot.db'), '--db', str(tmp / 'leads.db'), '--log', str(tmp / 'none.log'),
            '--min-seq', '2', '--port', '1', *extra]
    return subprocess.run(args, env={**os.environ, 'RESTORE_SCRIPT': str(RESTORE)},
                          capture_output=True, text=True, timeout=60), trace


def _setup(tmp, hot):
    _make(tmp / 'snapshot.db', [1, 2])
    _make(tmp / 'leads.db', [1, 2, 3])
    if hot:
        _hot_journal(tmp / 'leads.db')


def _server_view(db):
    """What the next server start would observe at this exact path. Opening is itself recovery."""
    if not db.exists():
        return None
    with sqlite3.connect(db) as c:
        assert c.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert c.execute('PRAGMA foreign_key_check').fetchall() == []
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert 'ghost' not in tables, 'uncommitted transaction became visible'
        return tuple(r[0] for r in c.execute('SELECT id FROM leads ORDER BY id'))


def _clean_ops(tmp, hot):
    tmp.mkdir()
    _setup(tmp, hot)
    r, trace = _run(tmp, 'none', -1, '--allow-rpo-gap')
    assert r.returncode == 0, r.stdout + r.stderr
    return len(json.loads(trace.read_text())['ops'])


@pytest.mark.parametrize('hot', [False, True], ids=['clean_old', 'hot_journal_old'])
@pytest.mark.parametrize('mode', ['kill_before', 'kill_after', 'ENOSPC', 'EIO'])
def test_every_filesystem_cutpoint_preserves_old_or_new_generation(tmp_path, mode, hot):
    total = _clean_ops(tmp_path / 'probe', hot)
    assert total >= 3, 'driver observed no filesystem operations'
    for i in range(total):
        work = tmp_path / f'cut{i}'
        work.mkdir()
        _setup(work, hot)
        r, _ = _run(work, mode, i, '--allow-rpo-gap')
        if mode.startswith('kill'):
            assert r.returncode == -9, f'cut {i} not reached: {r.stdout}{r.stderr}'
        view = _server_view(work / 'leads.db')
        assert view in ((1, 2, 3), (1, 2)), f'{mode} at op {i}: server would start on {view!r}'
        if mode in ('ENOSPC', 'EIO') and r.returncode != 0:
            assert 'restore OK' not in r.stdout
            if view == (1, 2):  # Only the post-rename directory sync may fail after publication.
                assert 'published_not_durable' in r.stderr, f'failed restore replaced the database at op {i}'
        # Interrupted restore can be repeated to completion without manual repair.
        r2, _ = _run(work, 'none', -1, '--allow-rpo-gap')
        assert r2.returncode == 0, f'rerun after {mode}@{i}: {r2.stderr}'
        assert _server_view(work / 'leads.db') == (1, 2)
        with sqlite3.connect(work / 'leads.db') as c:
            assert c.execute("SELECT seq FROM sqlite_sequence WHERE name='leads'").fetchone()[0] == 2


def test_new_generation_never_inherits_stale_sidecars(tmp_path):
    _setup(tmp_path, True)
    r, _ = _run(tmp_path, 'none', -1, '--allow-rpo-gap')
    assert r.returncode == 0, r.stderr
    assert not Path(f"{tmp_path / 'leads.db'}-journal").exists()
    assert not list(tmp_path.glob('*.part'))
    # The pre-restore copy (journal included) reproduces the old committed state.
    kept = sorted(p for p in tmp_path.glob('leads.db.pre-restore-*') if not p.name.endswith('-journal'))
    assert len(kept) == 1 and Path(f'{kept[0]}-journal').exists()
    assert _server_view(kept[0]) == (1, 2, 3)


def test_restore_refuses_snapshot_with_foreign_key_violations(tmp_path):
    _setup(tmp_path, False)
    with sqlite3.connect(tmp_path / 'snapshot.db') as c:
        c.execute("INSERT INTO outbox(lead_id,channel) VALUES(99,'webhook')")
    before = (tmp_path / 'leads.db').read_bytes()
    r, _ = _run(tmp_path, 'none', -1, '--allow-rpo-gap')
    assert r.returncode == 4 and 'foreign_key_violations=1' in r.stderr
    assert (tmp_path / 'leads.db').read_bytes() == before
