"""Backup/restore fault-injection: no false success, no silent replacement, no reused ID."""
import importlib.util
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

from test_leads import LEAD, srv  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent


def _module(db, out, keep):
    spec = importlib.util.spec_from_file_location('backup_fault_probe', ROOT / 'ops/backup.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.DB, mod.OUT, mod.KEEP = db, out, keep
    return mod


def _seed(db):
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE leads(id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT, type TEXT, payload TEXT)')
        conn.execute("INSERT INTO leads(created,type,payload) VALUES('2026','rent','{}')")


def test_missing_database_never_claims_success(tmp_path, capsys):
    out = tmp_path / 'backups'
    backup = _module(tmp_path / 'missing.db', out, 3)
    assert backup.main() == 1
    assert 'FAIL' in capsys.readouterr().err
    assert not list(out.glob('leads-*.db'))


def test_invalid_retention_is_fail_closed_before_mutating_files(tmp_path, capsys):
    db, out = tmp_path / 'leads.db', tmp_path / 'backups'
    _seed(db)
    backup = _module(db, out, 0)
    assert backup.main() == 1
    assert 'FAIL' in capsys.readouterr().err
    assert not out.exists()


def test_same_second_backups_preserve_both_recovery_points(tmp_path):
    db, out = tmp_path / 'leads.db', tmp_path / 'backups'
    _seed(db)
    backup = _module(db, out, 2)
    ticks = iter([100, 101])
    backup.time = SimpleNamespace(strftime=lambda _: '20261029-180000', time_ns=lambda: next(ticks))
    assert backup.main() == 0
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO leads(created,type,payload) VALUES('2026','rent','{}')")
    assert backup.main() == 0
    files = sorted(out.glob('leads-*.db'))
    assert len(files) == 2
    with sqlite3.connect(files[0]) as conn:
        assert conn.execute('SELECT count(*) FROM leads').fetchone() == (1,)
    with sqlite3.connect(files[1]) as conn:
        assert conn.execute('SELECT count(*) FROM leads').fetchone() == (2,)
    assert all(f.stat().st_mode & 0o777 == 0o600 for f in files)
    assert not list(out.glob('*.tmp'))


def test_exact_destination_collision_never_overwrites_previous_snapshot(tmp_path, capsys):
    db, out = tmp_path / 'leads.db', tmp_path / 'backups'
    _seed(db)
    backup = _module(db, out, 2)
    backup.time = SimpleNamespace(strftime=lambda _: '20261029-180000', time_ns=lambda: 123)
    assert backup.main() == 0
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO leads(created,type,payload) VALUES('2026','rent','{}')")
    assert backup.main() == 1
    assert 'FAIL' in capsys.readouterr().err
    files = list(out.glob('leads-*.db'))
    assert len(files) == 1 and not list(out.glob('*.tmp'))
    with sqlite3.connect(files[0]) as conn:
        assert conn.execute('SELECT count(*) FROM leads').fetchone() == (1,)


def test_restore_outbox_snapshot_preserves_pending_jobs_and_monotonic_id(srv, tmp_path):
    """Snapshot RPO has a real gap: the third later accepted lead is NOT recovered."""
    endpoint = 'http://127.0.0.1:9/hook'
    server = srv(DELIVERY_WORKER='0', LEAD_WEBHOOK_URL=endpoint, LEAD_WEBHOOK_SECRET='secret')
    for i in (1, 2):
        assert server.post(LEAD, f'k-recovery-{i:06d}')[1]['ref'] == f'PBT-{i:06d}'
    env = {**os.environ, 'LEAD_DB': str(server.db), 'BACKUP_DIR': str(tmp_path / 'backups')}
    backup = subprocess.run([sys.executable, str(ROOT / 'ops/backup.py')], env=env,
                            capture_output=True, text=True, timeout=15)
    assert backup.returncode == 0, backup.stdout + backup.stderr
    snapshot = next((tmp_path / 'backups').glob('leads-*.db'))
    with sqlite3.connect(snapshot) as conn:
        assert conn.execute("SELECT count(*) FROM outbox WHERE status='pending'").fetchone() == (2,)
    assert server.post(LEAD, 'k-recovery-000003')[1]['ref'] == 'PBT-000003'
    server.kill()
    cmd = [
        sys.executable, str(ROOT / 'ops/restore.py'), str(snapshot),
        '--db', str(server.db), '--log', str(tmp_path / 'missing.log'),
        '--min-seq', '3', '--port', str(server.port)
    ]
    denied = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    assert denied.returncode == 3 and 'known_RPO_gap=1' in denied.stderr
    with sqlite3.connect(server.db) as conn:
        assert conn.execute('SELECT id FROM leads ORDER BY id').fetchall() == [(1,), (2,), (3,)]
        assert conn.execute('SELECT count(*) FROM outbox').fetchone() == (3,)
    restore = subprocess.run(cmd + ['--allow-rpo-gap'], capture_output=True, text=True, timeout=15)
    assert restore.returncode == 0, restore.stdout + restore.stderr
    assert 'known_RPO_gap=1' in restore.stdout
    with sqlite3.connect(server.db) as conn:
        assert conn.execute('SELECT id FROM leads ORDER BY id').fetchall() == [(1,), (2,)]
        assert conn.execute("SELECT lead_id FROM outbox WHERE status='pending' ORDER BY lead_id").fetchall() == [(1,), (2,)]
    recovered = srv(DELIVERY_WORKER='0', LEAD_WEBHOOK_URL=endpoint, LEAD_WEBHOOK_SECRET='secret')
    assert recovered.post(LEAD, 'k-recovery-000004')[1]['ref'] == 'PBT-000004'
    assert recovered.rows('SELECT id FROM leads ORDER BY id') == [(1,), (2,), (4,)]


def test_backup_fsync_failure_cannot_report_success_or_publish(tmp_path, capsys):
    db, out = tmp_path / 'leads.db', tmp_path / 'backups'
    _seed(db)
    backup = _module(db, out, 3)

    def disk_failure(_):
        raise OSError('injected fsync failure')

    backup._sync_backup_file = disk_failure
    assert backup.main() == 1
    assert 'FAIL' in capsys.readouterr().err
    assert not list(out.glob('leads-*.db'))
    assert not list(out.glob('*.tmp'))


def test_backup_directory_sync_failure_is_reported_even_if_link_exists(tmp_path, capsys):
    db, out = tmp_path / 'leads.db', tmp_path / 'backups'
    _seed(db)
    backup = _module(db, out, 3)

    def directory_failure(_):
        raise OSError('injected metadata fsync failure')

    backup._sync_backup_directory = directory_failure
    assert backup.main() == 1
    assert 'FAIL' in capsys.readouterr().err
    snapshots = list(out.glob('leads-*.db'))
    assert len(snapshots) == 1  # Published atomically but not certified durable.
    with sqlite3.connect(snapshots[0]) as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def test_restore_negative_watermark_does_not_mutate_any_database(tmp_path):
    source = tmp_path / 'source.db'
    dest = tmp_path / 'production.db'
    _seed(source)
    _seed(dest)
    before = dest.read_bytes()
    result = subprocess.run([
        sys.executable, str(ROOT / 'ops/restore.py'), str(source),
        '--db', str(dest), '--log', str(tmp_path / 'missing.log'),
        '--min-seq', '-1', '--port', '0'
    ], capture_output=True, text=True, timeout=15)
    assert result.returncode == 1 and 'negative' in result.stderr
    assert dest.read_bytes() == before


def test_interrupted_backup_never_publishes_and_its_residue_is_removed(tmp_path):
    """SIGKILL at each namespace step: published snapshots stay whole, residue does not accumulate."""
    db, out = tmp_path / 'leads.db', tmp_path / 'backups'
    _seed(db)
    env = {**os.environ, 'LEAD_DB': str(db), 'BACKUP_DIR': str(out)}
    assert subprocess.run([sys.executable, str(ROOT / 'ops/backup.py')], env=env, timeout=15).returncode == 0
    driver = ("import os,runpy,signal,sys\nn=int(sys.argv[1])\nc=[0]\n"
              "def wrap(name):\n real=getattr(os,name)\n def f(*a,**k):\n"
              "  i=c[0];c[0]+=1\n  if i==n: os.kill(os.getpid(),signal.SIGKILL)\n  return real(*a,**k)\n"
              " setattr(os,name,f)\n"
              "for name in ('fsync','link','unlink'): wrap(name)\n"
              f"sys.argv=['backup.py']\nrunpy.run_path({str(ROOT / 'ops/backup.py')!r},run_name='__main__')\n")
    killed = 0
    for n in range(4):
        r = subprocess.run([sys.executable, '-c', driver, str(n)], env=env, timeout=15, capture_output=True)
        killed += r.returncode == -9
        for f in out.glob('leads-*.db'):
            with sqlite3.connect(f) as conn:
                assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
                assert conn.execute('SELECT count(*) FROM leads').fetchone() == (1,)
    assert killed >= 3, 'cutpoints were not exercised'
    assert subprocess.run([sys.executable, str(ROOT / 'ops/backup.py')], env=env, timeout=15).returncode == 0
    assert not list(out.glob('*.tmp'))


def test_restore_drill_measures_rpo_gap_and_never_claims_off_device(srv, tmp_path):
    server = srv(DELIVERY_WORKER='0', LEAD_WEBHOOK_URL='http://127.0.0.1:9/hook', LEAD_WEBHOOK_SECRET='s')
    for i in (1, 2):
        assert server.post(LEAD, f'k-drill-00{i:04d}')[0] == 201
    env = {**os.environ, 'LEAD_DB': str(server.db), 'BACKUP_DIR': str(tmp_path / 'b')}
    assert subprocess.run([sys.executable, str(ROOT / 'ops/backup.py')], env=env, timeout=15).returncode == 0
    snapshot = next((tmp_path / 'b').glob('leads-*.db'))
    before = server.db.read_bytes()
    run = subprocess.run([sys.executable, str(ROOT / 'ops/restore_drill.py'), str(snapshot), '--external-watermark', '3'],
                         capture_output=True, text=True, timeout=30)
    report = __import__('json').loads(run.stdout)
    assert run.returncode == 0, run.stdout
    assert report['rpo_gap_ids'] == 1 and report['restored_leads'] == 2 and report['pending_outbox'] == 2
    assert report['off_device'] is False and report['rpo_rto_policy'] == 'not_adopted'
    assert report['measured_rto_s'] >= 0
    assert server.db.read_bytes() == before
    assert server.post(LEAD, 'k-drill-after-1')[0] == 201  # The live server was untouched and still holds its guard.


BARRIER_DRIVER = r'''
import os, runpy, sys, time
reached, release = sys.argv[1], sys.argv[2]
real_fsync = os.fsync
state = {'done': False}
def fsync(fd):
    # First fsync is the temporary snapshot, just before create-only publication.
    if not state['done']:
        state['done'] = True
        open(reached, 'w').close()
        deadline = time.monotonic() + 20
        while not os.path.exists(release):
            if time.monotonic() > deadline:
                os._exit(97)
            time.sleep(.01)
    return real_fsync(fd)
os.fsync = fsync
sys.argv = ['backup.py']
runpy.run_path(os.environ['BACKUP_SCRIPT'], run_name='__main__')
'''


def test_concurrent_backup_never_destroys_a_running_backups_temporary_file(tmp_path):
    """Deterministic interleaving by file barrier: A holds its temporary snapshot, B runs to completion, A resumes."""
    db, out = tmp_path / 'leads.db', tmp_path / 'backups'
    _seed(db)
    env = {**os.environ, 'LEAD_DB': str(db), 'BACKUP_DIR': str(out), 'BACKUP_SCRIPT': str(ROOT / 'ops/backup.py')}
    assert subprocess.run([sys.executable, str(ROOT / 'ops/backup.py')], env=env, timeout=15).returncode == 0
    published = sorted(out.glob('leads-*.db'))
    before = {p: p.read_bytes() for p in published}
    reached, release = tmp_path / 'reached', tmp_path / 'release'
    a = subprocess.Popen([sys.executable, '-c', BARRIER_DRIVER, str(reached), str(release)], env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        for _ in range(1000):
            if reached.exists():
                break
            assert a.poll() is None, a.communicate()
            __import__('time').sleep(.01)
        assert reached.exists(), 'barrier not reached: the interleaving was not exercised'
        held = list(out.glob('leads-*.tmp'))
        assert len(held) == 1
        b = subprocess.run([sys.executable, str(ROOT / 'ops/backup.py')], env=env, capture_output=True, text=True, timeout=15)
        assert held[0].exists(), 'B removed the temporary file of a backup still running'
        assert b.returncode == 2 and 'REFUSED' in b.stderr, (b.returncode, b.stderr)
    finally:
        release.write_text('')
    stdout, stderr = a.communicate(timeout=20)
    assert a.returncode == 0, stderr
    assert 'backup OK' in stdout
    for path, raw in before.items():
        assert path.read_bytes() == raw, 'a published snapshot changed'
    snapshots = sorted(out.glob('leads-*.db'))
    assert len(snapshots) == 2 and not list(out.glob('*.tmp'))
    for snapshot in snapshots:
        with sqlite3.connect(snapshot) as conn:
            assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    # The lock died with its holder: nothing stale remains for the next timer tick.
    assert subprocess.run([sys.executable, str(ROOT / 'ops/backup.py')], env=env, timeout=15).returncode == 0


def test_backup_keeps_the_just_published_snapshot_after_clock_rollback(tmp_path):
    db, out = tmp_path / 'leads.db', tmp_path / 'backups'
    _seed(db)
    backup = _module(db, out, 1)
    dates = iter(('20261126-150000', '20261126-145900'))
    backup.time = SimpleNamespace(strftime=lambda _: next(dates), time_ns=lambda: 100)
    assert backup.main() == 0
    with sqlite3.connect(db) as connection:
        connection.execute("INSERT INTO leads(created,type,payload) VALUES('2026','rent','{}')")
    assert backup.main() == 0
    snapshots = list(out.glob('leads-*.db'))
    assert [path.name for path in snapshots] == ['leads-20261126-145900-000000100.db']
    with sqlite3.connect(snapshots[0]) as connection:
        assert connection.execute('SELECT count(*) FROM leads').fetchone() == (2,)


def test_restore_drill_counts_gaps_without_allocating_the_watermark_range(tmp_path, monkeypatch):
    from ops import restore_drill

    def no_materialization(*_):
        raise AssertionError('restore drill must not enumerate accepted IDs')

    monkeypatch.setattr(restore_drill, 'range', no_materialization, raising=False)
    snapshot = tmp_path / 'snapshot.db'
    _seed(snapshot)
    with sqlite3.connect(snapshot) as connection:
        connection.execute('CREATE TABLE outbox(lead_id INTEGER REFERENCES leads(id), status TEXT)')
        connection.execute("INSERT INTO outbox(lead_id,status) VALUES (1,'pending')")
    watermark = 10**12
    report = restore_drill.drill(snapshot, watermark)
    assert report['status'] == 'PASS'
    assert report['restored_leads'] == 1 and report['highest_restored_id'] == 1
    assert report['rpo_gap_ids'] == watermark - 1


def test_backup_defaults_follow_the_configured_state_directory(tmp_path, monkeypatch):
    import runpy

    state = tmp_path / 'state'
    monkeypatch.setenv('PBT_DATA_DIR', str(state))
    monkeypatch.delenv('LEAD_DB', raising=False)
    monkeypatch.delenv('BACKUP_DIR', raising=False)
    backup = runpy.run_path(str(ROOT / 'ops/backup.py'))
    assert backup['DB'] == state / 'leads.db'
    assert backup['OUT'] == state / 'backups'

    override = tmp_path / 'independent-store'
    monkeypatch.setenv('BACKUP_DIR', str(override))
    backup = runpy.run_path(str(ROOT / 'ops/backup.py'))
    assert backup['DB'] == state / 'leads.db'
    assert backup['OUT'] == override
