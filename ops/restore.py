#!/usr/bin/env python3
"""Відновлення бази заявок з бекапу (OPS-1). id заявки — AUTOINCREMENT, монотонний лише в межах файлу: після відкату до знімка
sqlite_sequence повертається назад, і номери LA-NNNNNN з вікна «бекап → збій» видаються вдруге (вебхук дедуплікує за id).
Тому після копіювання лічильник піднімається до max(знімок, N з журналу 'lead stored id=N', --min-seq).

Fail-closed: сервер відповідає на своєму порту → відмова (код 2); журналу нема / в ньому нема жодного 'lead stored' і не
задано --min-seq → відмова (код 1): журнал лежить у тому ж data/, що й БД, тож може загинути разом з нею.
Поточна база (і її -journal/-wal/-shm) не видаляється, а відкладається як <db>.pre-restore-<час>.

  python3 ops/restore.py data/backups/leads-YYYYmmdd-HHMMSS.db [--db PATH] [--log PATH] [--min-seq N] [--host H] [--port P]
"""
import argparse, os, re, socket, sqlite3, sys, time
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


def main(argv=None):
    ap = argparse.ArgumentParser(description='restore leads.db from backup with a monotonic id sequence')
    ap.add_argument('backup')
    ap.add_argument('--db', default=os.environ.get('LEAD_DB') or str(ROOT / 'data' / 'leads.db'))
    ap.add_argument('--log', default=str(ROOT / 'data' / 'server.log'))
    ap.add_argument('--min-seq', type=int, default=None)
    ap.add_argument('--host', default=os.environ.get('HOST') or '127.0.0.1')
    ap.add_argument('--port', type=int, default=int(os.environ.get('PORT') or 4180))
    a = ap.parse_args(argv)
    if server_answers(a.host, a.port):
        print(f'restore REFUSED: сервер відповідає на {a.host}:{a.port} — спершу зупини його', file=sys.stderr); return 2
    src, dst = Path(a.backup), Path(a.db)
    if not src.is_file():
        print(f'restore FAIL: бекапу нема ({src})', file=sys.stderr); return 1
    n_log = log_max(a.log)
    if n_log is None and a.min_seq is None:
        print(f'restore FAIL: у журналі {a.log} нема "lead stored id=N" і не задано --min-seq — '
              'максимальний виданий id невідомий, відновлення дало б повторні номери заявок', file=sys.stderr); return 1
    tmp = dst.with_name(dst.name + '.restore-tmp')
    tmp.unlink(missing_ok=True)
    s = sqlite3.connect(f'file:{src}?mode=ro', uri=True)
    with sqlite3.connect(tmp) as t:
        s.backup(t)
    s.close()
    c = sqlite3.connect(tmp)
    try:
        if c.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('integrity_check копії не ok')
        row = c.execute("SELECT seq FROM sqlite_sequence WHERE name='leads'").fetchone()
        snap = max(row[0] if row else 0, c.execute('SELECT coalesce(max(id), 0) FROM leads').fetchone()[0])
        seq = max(snap, n_log or 0, a.min_seq or 0)
        if row:
            c.execute("UPDATE sqlite_sequence SET seq=? WHERE name='leads'", (seq,))
        else:
            c.execute("INSERT INTO sqlite_sequence(name, seq) VALUES('leads', ?)", (seq,))
        c.commit()
        if c.execute("SELECT seq FROM sqlite_sequence WHERE name='leads'").fetchone()[0] != seq:
            raise RuntimeError('sqlite_sequence не записано')
    except Exception as e:  # noqa: BLE001
        c.close(); tmp.unlink(missing_ok=True)
        print(f'restore FAIL: {e}', file=sys.stderr); return 1
    c.close()
    if server_answers(a.host, a.port):          # сервер піднявся, поки готувалася копія
        tmp.unlink(missing_ok=True)
        print(f'restore REFUSED: сервер відповідає на {a.host}:{a.port}', file=sys.stderr); return 2
    stamp = time.strftime('%Y%m%d-%H%M%S')
    for suf in ('', '-journal', '-wal', '-shm'):
        f = Path(str(dst) + suf)
        if f.exists():
            f.replace(Path(f'{dst}.pre-restore-{stamp}{suf}'))
    os.chmod(tmp, 0o600); tmp.replace(dst)
    print(f'restore OK: {src.name} → {dst} seq={seq} (знімок={snap} журнал={n_log} min-seq={a.min_seq})'); return 0


if __name__ == '__main__':
    sys.exit(main())
