#!/usr/bin/env python3
"""Run the unmodified server/app.py with a process-death cutpoint injected from outside.

No production test hook exists: this wrapper substitutes the sqlite3 connection
factory and selected module attributes, then SIGKILLs itself at the named point.
SIGKILL (not an exception) means no finally block, rollback or flush can run.

  PBT_CUT = before_begin | after_insert | after_outbox | before_commit |
            after_commit | before_reply | after_remote_ack
  PBT_ALLOW_SECOND_SERVER = 1 bypasses the single-process guard (concurrency tests)
"""
import importlib.util
import os
from pathlib import Path
import signal
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
CUT = os.environ.get('PBT_CUT', '')
REAL_LEAD_INSERT = 'INSERT INTO leads(created,type,payload,ip_hash'


def die():
    os.kill(os.getpid(), signal.SIGKILL)


class CutConnection(sqlite3.Connection):
    def execute(self, sql, *args):
        if CUT == 'before_begin' and sql == 'BEGIN IMMEDIATE':
            die()
        result = super().execute(sql, *args)
        if CUT == 'after_insert' and sql.startswith(REAL_LEAD_INSERT):
            die()
        return result

    def executemany(self, sql, *args):
        result = super().executemany(sql, *args)
        if CUT == 'after_outbox' and sql.startswith('INSERT INTO outbox'):
            die()
        return result

    def commit(self):
        lead_tx = self.in_transaction and self.total_changes > 0 and getattr(self, '_lead_tx', True)
        if CUT == 'before_commit' and lead_tx:
            die()
        super().commit()
        if CUT == 'after_commit' and lead_tx:
            die()


_connect = sqlite3.connect
sqlite3.connect = lambda *a, **k: _connect(*a, **{'factory': CutConnection, **k})

_saved_cut, CUT = CUT, ''  # Schema migration at import is not the operation under test.
spec = importlib.util.spec_from_file_location('app', ROOT / 'server' / 'app.py')
app = importlib.util.module_from_spec(spec)
sys.modules['app'] = app
spec.loader.exec_module(app)
CUT = _saved_cut

if CUT == 'before_reply':
    _send_json = app.Handler.send_json

    def send_json(self, code, obj):
        if code == 201:
            die()
        return _send_json(self, code, obj)

    app.Handler.send_json = send_json

if CUT == 'after_remote_ack':
    _attempt = app._attempt_delivery

    def attempt(row):
        result = _attempt(row)
        if result[0] is None:
            die()  # Remote acknowledged; the local status write never happens.
        return result

    app._attempt_delivery = attempt

if os.environ.get('PBT_ALLOW_SECOND_SERVER') == '1':
    app.acquire_single_process_guard = lambda: None
    app._try_migrate(5)  # This process lost the guard at import, so it skipped boot migration.

app.main()
