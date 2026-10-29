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
    restore = subprocess.run([
        sys.executable, str(ROOT / 'ops/restore.py'), str(snapshot),
        '--db', str(server.db), '--log', str(tmp_path / 'missing.log'),
        '--min-seq', '3', '--port', str(server.port)
    ], capture_output=True, text=True, timeout=15)
    assert restore.returncode == 0, restore.stdout + restore.stderr
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
