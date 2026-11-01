"""OPS-01: every signal claims exactly what it observed; unobserved evidence is UNKNOWN, never ready."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / 'ops' / 'readiness.py'


def _db(path, *, pending=0, failed=0, delivered=0, age=0.0, heartbeat_age=1.0):
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE leads(id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT NOT NULL, type TEXT, payload TEXT)')
        c.execute('''CREATE TABLE outbox(id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER NOT NULL REFERENCES leads(id),
                     channel TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
                     next_at REAL NOT NULL DEFAULT 0, last_at REAL, last_error TEXT, delivered_at TEXT)''')
        c.execute('CREATE TABLE runtime_heartbeat(name TEXT PRIMARY KEY, observed_at REAL NOT NULL)')
        if heartbeat_age is not None:
            c.execute("INSERT INTO runtime_heartbeat VALUES('delivery', ?)", (time.time() - heartbeat_age,))
        created = time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime(time.time() - age))
        for status, n in (('pending', pending), ('failed', failed), ('delivered', delivered)):
            for _ in range(n):
                lead = c.execute("INSERT INTO leads(created,type,payload) VALUES(?, 'rent', '{}')", (created,)).lastrowid
                c.execute('INSERT INTO outbox(lead_id,channel,status) VALUES(?,?,?)', (lead, 'webhook', status))


def _run(db, *extra):
    r = subprocess.run([sys.executable, str(TOOL), '--db', str(db), '--max-pending-age-s', '60',
                        '--max-worker-idle-s', '60', *extra], capture_output=True, text=True, timeout=20)
    return r.returncode, json.loads(r.stdout)


def test_fresh_heartbeat_with_stale_backlog_is_not_ready(tmp_path):
    db = tmp_path / 'l.db'
    _db(db, pending=100, age=3600, heartbeat_age=1)
    code, out = _run(db)
    assert code == 1 and out['ready'] is False
    assert out['signals']['worker_activity'] == 'PASS'
    assert out['signals']['delivery_backlog'] == 'FAIL'


def test_clean_local_state_never_claims_receiver_or_business_truth(tmp_path):
    db = tmp_path / 'l.db'
    _db(db, delivered=5)
    code, out = _run(db)
    assert out['signals']['storage_snapshot'] == 'PASS' and out['signals']['delivery_backlog'] == 'PASS'
    assert out['signals']['transport_ack'] == 'PASS'
    assert out['signals']['receiver_persistence'] == 'UNKNOWN'
    assert out['signals']['business_processing'] == 'UNKNOWN'
    assert code == 2 and out['ready'] is False, 'unknown mandatory evidence must block readiness'


def test_no_delivery_rows_means_transport_unknown_not_pass(tmp_path):
    db = tmp_path / 'l.db'
    _db(db)
    _, out = _run(db)
    assert out['signals']['transport_ack'] == 'UNKNOWN'


def test_failed_terminal_rows_fail_and_missing_heartbeat_is_unknown(tmp_path):
    db = tmp_path / 'l.db'
    _db(db, failed=1, heartbeat_age=None)
    code, out = _run(db)
    assert code == 1
    assert out['signals']['delivery_terminal_failures'] == 'FAIL'
    assert out['signals']['worker_activity'] == 'UNKNOWN'


def test_unreadable_database_is_unknown_and_output_has_no_payload(tmp_path):
    code, out = _run(tmp_path / 'absent.db')
    assert code == 2 and out['ready'] is False and out['signals']['storage_snapshot'] == 'UNKNOWN'
    db = tmp_path / 'p.db'
    _db(db, pending=1)
    with sqlite3.connect(db) as c:
        c.execute("UPDATE leads SET payload='{\"contact\":\"+380970000000\"}'")
    r = subprocess.run([sys.executable, str(TOOL), '--db', str(db), '--max-pending-age-s', '60',
                        '--max-worker-idle-s', '60'], capture_output=True, text=True, timeout=20)
    assert '380970000000' not in r.stdout + r.stderr


def test_external_receipt_requires_matching_ids_not_a_self_written_flag(tmp_path):
    db = tmp_path / 'l.db'
    _db(db, delivered=2)
    receipt = tmp_path / 'r.json'
    receipt.write_text(json.dumps({'schema': 'pbt-receiver-receipt-v1', 'receipt_id': 'R-1', 'receiver': 'crm',
                                   'persisted_lead_ids': [1, 2]}))
    _, out = _run(db, '--receiver-receipt', str(receipt))
    assert out['signals']['receiver_persistence'] == 'PASS'
    assert out['signals']['business_processing'] == 'UNKNOWN', 'persistence is not business processing'
    receipt.write_text(json.dumps({'schema': 'pbt-receiver-receipt-v1', 'receipt_id': 'R-1', 'receiver': 'crm',
                                   'persisted_lead_ids': [1]}))
    _, out = _run(db, '--receiver-receipt', str(receipt))
    assert out['signals']['receiver_persistence'] == 'FAIL'
    receipt.write_text(json.dumps({'ok': True}))
    _, out = _run(db, '--receiver-receipt', str(receipt))
    assert out['signals']['receiver_persistence'] == 'UNKNOWN'
