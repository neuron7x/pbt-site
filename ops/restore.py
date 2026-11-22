#!/usr/bin/env python3
"""Відновлення бази заявок з бекапу (OPS-1). id заявки — AUTOINCREMENT, монотонний лише в межах файлу: після відкату до знімка
sqlite_sequence повертається назад, і номери LA-NNNNNN з вікна «бекап → збій» видаються вдруге (вебхук дедуплікує за id).
Тому після копіювання лічильник піднімається до max(знімок, N з журналу 'lead stored id=N', --min-seq).
Незворотна втрата прийнятих заявок між snapshot та останнім виданим ID заборонена за замовчуванням:
код 3 (REFUSED) і поточна БД залишається незмінною. Break-glass --allow-rpo-gap допускається лише після
позафайлової звірки втрачених заявок; прапорець НЕ повертає їх автоматично.

Fail-closed: сервер відповідає на своєму порту → відмова (код 2); журналу нема / в ньому нема жодного 'lead stored' і не
задано --min-seq → відмова (код 1): журнал лежить у тому ж data/, що й БД, тож може загинути разом з нею.
Поточна база (і її -journal/-wal/-shm) не видаляється: її байти стало копіюються в <db>.pre-restore-<час>[-sidecar].

Crash safety: the existing database stays at its path until a single atomic rename publishes the
validated new generation, so every interruption leaves the old or the new database in place.
Sidecars belong to the old generation and would corrupt the new one (a hot journal rolls back into
whatever file now has that name); the old database is settled first, so removing them is safe.

  python3 ops/restore.py data/backups/leads-YYYYmmdd-HHMMSS.db [--db PATH] [--log PATH] [--min-seq N] [--host H] [--port P]
"""
import argparse, fcntl, os, re, socket, sqlite3, sys, time
from contextlib import closing
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
# Лише повний запис app.py (формат '%(asctime)s %(levelname)s %(message)s', log.info('lead stored id=%s type=%s outbox=%s')) від
# початку рядка; той самий текст усередині іншого запису (Origin, рядок запиту) — дані клієнта, не джерело seq.
STORED = re.compile(rb'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} INFO lead stored id=(\d+) type=\w+ outbox=', re.M)


def log_max(path):
    try:
        return max((int(m.group(1)) for m in STORED.finditer(Path(path).read_bytes())), default=None)
    except OSError:
        return None


def server_answers(host, port):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


SIDECARS = ('-journal', '-wal', '-shm')


class PublishedNotDurable(Exception):
    """The new generation is live but the rename is not certified to survive power loss."""


def _fsync_path(path, flags=os.O_RDONLY):
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_dir(directory):
    _fsync_path(directory, os.O_RDONLY | os.O_DIRECTORY)


def _private_writer(path):
    """Create-only and private from the first byte, regardless of the caller's umask."""
    return open(path, 'xb', opener=lambda name, flags: os.open(name, flags, 0o600))


def _staging_parts(dst):
    """Назва БД є буквальним префіксом, навіть якщо містить [], * або ?."""
    prefix = dst.name + '.pre-restore-'
    return [path for path in dst.parent.iterdir()
            if path.name.startswith(prefix) and path.name.endswith('.part')]


def _durable_copy(src, dst):
    """Copy, not hard link: recovery of the live file must never rewrite the preserved evidence."""
    part = Path(f'{dst}.part')
    with src.open('rb') as reader, _private_writer(part) as writer:
        while chunk := reader.read(1024 * 1024):
            writer.write(chunk)
        writer.flush()
        os.fsync(writer.fileno())
    os.chmod(part, 0o600)
    os.replace(part, dst)
    _fsync_dir(dst.parent)


def _settle(path):
    """Let SQLite roll back a hot journal / checkpoint a WAL, so the main file alone is consistent.
    A corrupt old database is exactly why restores happen: its raw bytes are already preserved."""
    try:
        with closing(sqlite3.connect(path, timeout=5)) as c:
            c.execute('SELECT count(*) FROM sqlite_master').fetchone()
    except sqlite3.Error:
        pass


def _publish(tmp, dst):
    os.chmod(tmp, 0o600)
    _fsync_path(tmp)
    _fsync_dir(dst.parent)
    stamp = time.strftime('%Y%m%d-%H%M%S') + f'-{time.time_ns() % 1_000_000_000:09d}'
    present = [suf for suf in ('',) + SIDECARS if Path(f'{dst}{suf}').exists()]
    for suf in present:
        _durable_copy(Path(f'{dst}{suf}'), Path(f'{dst}.pre-restore-{stamp}{suf}'))
    if '' in present:
        _settle(dst)
    removed = False
    for suf in SIDECARS:
        f = Path(f'{dst}{suf}')
        if f.exists():
            f.unlink()
            removed = True
    if removed:   # A sidecar reappearing next to the new generation after power loss would corrupt it.
        _fsync_dir(dst.parent)
    os.replace(tmp, dst)
    try:
        _fsync_dir(dst.parent)
    except OSError as e:
        raise PublishedNotDurable(type(e).__name__) from None


def main(argv=None):
    ap = argparse.ArgumentParser(description='restore leads.db from backup with a monotonic id sequence')
    ap.add_argument('backup')
    ap.add_argument('--db', default=os.environ.get('LEAD_DB') or str(ROOT / 'data' / 'leads.db'))
    ap.add_argument('--log', default=str(ROOT / 'data' / 'server.log'))
    ap.add_argument('--min-seq', type=int, default=None)
    ap.add_argument('--allow-rpo-gap', action='store_true',
                    help='explicit break-glass acknowledgment of unrecoverable accepted leads after the snapshot')
    ap.add_argument('--allow-fk-violations', action='store_true',
                    help='explicit acknowledgment that the snapshot contains orphan references')
    ap.add_argument('--host', default=os.environ.get('HOST') or '127.0.0.1')
    ap.add_argument('--port', type=int, default=int(os.environ.get('PORT') or 4180))
    a = ap.parse_args(argv)
    if a.min_seq is not None and a.min_seq < 0:
        print('restore FAIL: negative --min-seq invalid', file=sys.stderr); return 1
    if server_answers(a.host, a.port):
        print(f'restore REFUSED: сервер відповідає на {a.host}:{a.port} — спершу зупини його', file=sys.stderr); return 2
    src, dst = Path(a.backup), Path(a.db)
    if not src.is_file():
        print(f'restore FAIL: бекапу нема ({src})', file=sys.stderr); return 1
    try:
        tmp = dst.with_name(dst.name + '.restore-tmp')
        source = src.resolve()
        staging = [tmp, *_staging_parts(dst)]
        if any(path.resolve() == source for path in staging):
            print('restore REFUSED: backup path conflicts with restore staging', file=sys.stderr)
            return 1
    except (OSError, RuntimeError, ValueError):
        print('restore FAIL: restore staging paths cannot be verified', file=sys.stderr)
        return 1
    n_log = log_max(a.log)
    if n_log is None and a.min_seq is None:
        print(f'restore FAIL: у журналі {a.log} нема "lead stored id=N" і не задано --min-seq — '
              'максимальний виданий id невідомий, відновлення дало б повторні номери заявок', file=sys.stderr); return 1
    guard = os.open(f'{dst}.server-lock', os.O_RDWR | os.O_CREAT, 0o600)   # Held until exit: no server can start mid-restore.
    try:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(guard)
        print('restore REFUSED: single_process_guard held — a server is using this database', file=sys.stderr); return 2
    try:
        tmp.unlink(missing_ok=True)
        for stale in _staging_parts(dst):
            stale.unlink()
        # SQLite must inherit an owner-only file, not create a readable staging
        # database that a crash could leave behind before _publish() chmods it.
        with _private_writer(tmp):
            pass
        with closing(sqlite3.connect(src.resolve().as_uri() + '?mode=ro', uri=True)) as s, closing(sqlite3.connect(tmp)) as t:
            s.backup(t)
        with closing(sqlite3.connect(tmp)) as c:
            if c.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('integrity_check копії не ok')
            orphans = len(c.execute('PRAGMA foreign_key_check').fetchall())
            if orphans and not a.allow_fk_violations:
                print(f'restore REFUSED: foreign_key_violations={orphans}; '
                      'reconcile the snapshot before explicit --allow-fk-violations', file=sys.stderr)
                tmp.unlink(missing_ok=True)
                return 4
            row = c.execute("SELECT seq FROM sqlite_sequence WHERE name='leads'").fetchone()
            snap = max(row[0] if row else 0, c.execute('SELECT coalesce(max(id), 0) FROM leads').fetchone()[0])
            seq = max(snap, n_log or 0, a.min_seq or 0)
            # A higher externally issued watermark proves a known RPO gap. Raising
            # sqlite_sequence avoids ID reuse but never restores the missing leads.
            # Never silently discard accepted outbox jobs on routine restore.
            if seq > snap and not a.allow_rpo_gap:
                print(f'restore REFUSED: known_RPO_gap={seq-snap}; '
                      'reconcile missing accepted leads before explicit --allow-rpo-gap', file=sys.stderr)
                tmp.unlink(missing_ok=True)
                return 3
            if row:
                c.execute("UPDATE sqlite_sequence SET seq=? WHERE name='leads'", (seq,))
            else:
                c.execute("INSERT INTO sqlite_sequence(name, seq) VALUES('leads', ?)", (seq,))
            c.commit()
            if c.execute("SELECT seq FROM sqlite_sequence WHERE name='leads'").fetchone()[0] != seq:
                raise RuntimeError('sqlite_sequence не записано')
        if server_answers(a.host, a.port):          # сервер піднявся, поки готувалася копія
            tmp.unlink(missing_ok=True)
            print(f'restore REFUSED: сервер відповідає на {a.host}:{a.port}', file=sys.stderr); return 2
        _publish(tmp, dst)
    except PublishedNotDurable as e:
        print(f'restore FAIL: published_not_durable {e}: rerun to certify', file=sys.stderr); return 1
    except (OSError, sqlite3.Error, RuntimeError) as e:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        print(f'restore FAIL: {type(e).__name__}: {e}', file=sys.stderr); return 1
    print(f'restore OK: {src.name} → {dst} seq={seq} known_RPO_gap={seq-snap} '
          f'(знімок={snap} журнал={n_log} min-seq={a.min_seq})'); return 0


if __name__ == '__main__':
    sys.exit(main())
