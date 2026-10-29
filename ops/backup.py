#!/usr/bin/env python3
"""Fail-closed, collision-safe SQLite online backup of accepted leads and outbox.

A snapshot is only successful after SQLite integrity_check, an atomic
create-only publish, and retention. No existing snapshot is ever overwritten.
"""
import os
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = Path(os.environ.get('LEAD_DB') or ROOT / 'data' / 'leads.db')
OUT = Path(os.environ.get('BACKUP_DIR') or ROOT / 'data' / 'backups')
KEEP = int(os.environ.get('BACKUP_KEEP') or 14)


def _sync_backup_file(path):
    with path.open('rb') as handle:
        os.fsync(handle.fileno())


def _sync_backup_directory(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def main():
    if KEEP < 1:
        print('backup FAIL: BACKUP_KEEP must be positive', file=sys.stderr)
        return 1
    if not DB.is_file():
        print('backup FAIL: source database does not exist', file=sys.stderr)
        return 1

    tmp = None
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        os.chmod(OUT, 0o700)
        stamp = time.strftime('%Y%m%d-%H%M%S')
        # A create-only publication also protects against clock/ID collisions.
        dst = OUT / f'leads-{stamp}-{time.time_ns() % 1_000_000_000:09d}.db'
        tmp = dst.with_suffix('.tmp')
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)

        with closing(sqlite3.connect(DB.resolve().as_uri() + '?mode=ro', uri=True)) as source:
            with closing(sqlite3.connect(tmp)) as copy:
                source.backup(copy)
        with closing(sqlite3.connect(tmp)) as copy:
            result = copy.execute('PRAGMA integrity_check').fetchone()[0]
            if result != 'ok':
                raise RuntimeError('backup integrity check failed')
            count = copy.execute('SELECT count(*) FROM leads').fetchone()[0]

        os.chmod(tmp, 0o600)
        _sync_backup_file(tmp)   # Durable content must precede the namespace publication.
        os.link(tmp, dst)  # Atomic no-replace; FileExistsError is a hard failure.
        _sync_backup_directory(OUT)  # Persist the new name before returning success.
        tmp.unlink()
        tmp = None

        previous = sorted(OUT.glob('leads-*.db'))[:-KEEP]
        for entry in previous:
            entry.unlink()
        print(f'backup OK: {dst.name} заявок={count} видалено старих={len(previous)}')
        return 0
    except (OSError, sqlite3.DatabaseError, RuntimeError) as exc:
        # Never print customer data, raw database contents or private paths.
        print(f'backup FAIL: {type(exc).__name__}', file=sys.stderr)
        return 1
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


if __name__ == '__main__':
    sys.exit(main())
