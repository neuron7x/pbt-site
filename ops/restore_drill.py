#!/usr/bin/env python3
"""Rehearse a restore into a disposable directory and measure it. Never touches the live database.

Reports elapsed RTO, the RPO gap against an external id watermark, and the accepted-lead/outbox
reconciliation of the restored copy. Local runs carry off_device=false and prove the procedure only:
DB-07/DB-08 need this run on a separate host, from an independently stored encrypted snapshot, with the
watermark taken from outside the failed machine. Thresholds are for the owner to adopt; none is assumed.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent


def drill(snapshot, watermark, off_device_receipt=None):
    with tempfile.TemporaryDirectory(prefix='pbt-restore-drill-') as scratch:
        target = Path(scratch) / 'leads.db'
        started = time.monotonic()
        run = subprocess.run([sys.executable, str(HERE / 'restore.py'), str(snapshot), '--db', str(target),
                              '--log', str(Path(scratch) / 'absent.log'), '--min-seq', str(watermark),
                              '--allow-rpo-gap', '--port', '1'], capture_output=True, text=True, timeout=600)
        elapsed = time.monotonic() - started
        if run.returncode != 0:
            return {'status': 'FAIL', 'reason': 'restore_refused', 'restore_exit': run.returncode}
        with sqlite3.connect(target) as c:
            integrity = c.execute('PRAGMA integrity_check').fetchone()[0]
            orphans = len(c.execute('PRAGMA foreign_key_check').fetchall())
            ids = {r[0] for r in c.execute('SELECT id FROM leads')}
            without_outbox = c.execute('SELECT count(*) FROM leads l WHERE NOT EXISTS (SELECT 1 FROM outbox o WHERE o.lead_id=l.id)').fetchone()[0]
            pending = c.execute("SELECT count(*) FROM outbox WHERE status='pending'").fetchone()[0]
            seq = c.execute("SELECT seq FROM sqlite_sequence WHERE name='leads'").fetchone()[0]
    highest = max(ids, default=0)
    missing = sorted(set(range(1, watermark + 1)) - ids)
    ok = integrity == 'ok' and not orphans and seq >= watermark
    return {'status': 'PASS' if ok else 'FAIL', 'measured_rto_s': round(elapsed, 3), 'restored_leads': len(ids),
            'highest_restored_id': highest, 'external_watermark': watermark, 'rpo_gap_ids': len(missing), 'pending_outbox': pending,
            'leads_without_outbox_row': without_outbox, 'integrity': integrity, 'foreign_key_violations': orphans,
            'off_device': bool(off_device_receipt), 'off_device_receipt': off_device_receipt,
            'scope': 'procedure rehearsal' if not off_device_receipt else 'caller-supplied receipt, verify its provenance',
            'rpo_rto_policy': 'not_adopted'}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('snapshot', type=Path)
    p.add_argument('--external-watermark', type=int, required=True, help='highest issued lead id, from outside this machine')
    p.add_argument('--off-device-receipt', default=None)
    a = p.parse_args(argv)
    if a.external_watermark < 0 or not a.snapshot.is_file():
        print(json.dumps({'status': 'FAIL', 'reason': 'invalid_input'}))
        return 2
    result = drill(a.snapshot, a.external_watermark, a.off_device_receipt)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
