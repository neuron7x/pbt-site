#!/usr/bin/env python3
"""Резервна копія бази заявок (O2): онлайн-бекап SQLite (узгоджений знімок без зупинки сервера) →
PRAGMA integrity_check КОПІЇ → атомарне перейменування → ротація KEEP найновіших. Код 1 при будь-якій помилці перевірки."""
import os, sqlite3, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
DB = Path(os.environ.get('LEAD_DB') or ROOT / 'data' / 'leads.db')
OUT = Path(os.environ.get('BACKUP_DIR') or ROOT / 'data' / 'backups'); KEEP = int(os.environ.get('BACKUP_KEEP') or 14)


def main():
    if not DB.exists():
        print(f'backup: бази нема ({DB}) — нічого копіювати'); return 0
    OUT.mkdir(parents=True, exist_ok=True); os.chmod(OUT, 0o700)
    dst = OUT / f'leads-{time.strftime("%Y%m%d-%H%M%S")}.db'; tmp = dst.with_suffix('.tmp')
    src = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    with sqlite3.connect(tmp) as b:
        src.backup(b)
    src.close()
    with sqlite3.connect(tmp) as b:
        res = b.execute('PRAGMA integrity_check').fetchone()[0]; n = b.execute('SELECT count(*) FROM leads').fetchone()[0]
    if res != 'ok':
        tmp.unlink(missing_ok=True); print(f'backup FAIL: integrity_check={res}', file=sys.stderr); return 1
    os.chmod(tmp, 0o600); tmp.replace(dst)
    old = sorted(OUT.glob('leads-*.db'))[:-KEEP]
    for f in old:
        f.unlink()
    print(f'backup OK: {dst.name} заявок={n} видалено старих={len(old)}'); return 0


if __name__ == '__main__':
    sys.exit(main())
