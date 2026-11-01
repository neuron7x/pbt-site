"""Local synthetic database checks for unverifiable outbox timestamps."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

import pytest

TOOL = Path(__file__).resolve().parents[1] / 'ops' / 'outbox_health.py'
spec = importlib.util.spec_from_file_location('outbox_health_clock_test', TOOL)
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


def database(path, *, created=None, heartbeat=None):
    with sqlite3.connect(path) as db:
        db.executescript('''
            CREATE TABLE leads(id INTEGER PRIMARY KEY, created TEXT);
            CREATE TABLE outbox(lead_id INTEGER, status TEXT, next_at REAL);
            CREATE TABLE runtime_heartbeat(name TEXT, observed_at REAL);
        ''')
        if created is not None:
            db.execute('INSERT INTO leads VALUES(1, ?)', (created,))
            db.execute("INSERT INTO outbox VALUES(1, 'pending', 0)")
        if heartbeat is not None:
            db.execute("INSERT INTO runtime_heartbeat VALUES('delivery', ?)", (heartbeat,))


def stamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


@pytest.mark.parametrize('kind', ['lead', 'heartbeat'])
def test_future_timestamp_rejected_beyond_clock_skew(tmp_path, kind):
    now = 1700000000.0
    db = tmp_path / 'synthetic.db'
    database(db, created=stamp(now + 1.001) if kind == 'lead' else None,
             heartbeat=now + 1.001 if kind == 'heartbeat' else None)
    with pytest.raises(ValueError):
        health.snapshot(db, now)


@pytest.mark.parametrize('kind', ['lead', 'heartbeat'])
def test_future_timestamp_inside_clock_skew_is_zero_age(tmp_path, kind):
    now = 1700000000.0
    db = tmp_path / 'synthetic.db'
    database(db, created=stamp(now + 1) if kind == 'lead' else None,
             heartbeat=now + 1 if kind == 'heartbeat' else None)
    report = health.snapshot(db, now)
    assert report['oldest_pending_age_s' if kind == 'lead' else 'worker_heartbeat_age_s'] == 0


@pytest.mark.parametrize('kind', ['lead', 'heartbeat'])
def test_future_timestamp_cli_is_unknown_without_data_leak(tmp_path, kind):
    now = time.time()
    db = tmp_path / 'synthetic.db'
    database(db, created=stamp(now + 3600) if kind == 'lead' else None,
             heartbeat=now + 3600 if kind == 'heartbeat' else now)
    result = subprocess.run([sys.executable, str(TOOL), '--db', str(db),
                             '--max-pending-age-s', '600', '--max-worker-idle-s', '5'],
                            capture_output=True, text=True, timeout=10, check=False)
    report = json.loads(result.stdout)
    assert result.returncode == 2 and not result.stderr
    assert report['status'] == 'unknown' and not report['ok']
    assert str(db) not in result.stdout


@pytest.mark.parametrize('value', ['broken', 'nan', 'inf', '-inf', float('inf'), float('-inf')])
def test_invalid_heartbeat_timestamp_is_unknown(tmp_path, value):
    db = tmp_path / 'synthetic.db'
    database(db, heartbeat=value)
    result = subprocess.run([sys.executable, str(TOOL), '--db', str(db),
                             '--max-pending-age-s', '600', '--max-worker-idle-s', '5'],
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 2 and not result.stderr
    assert json.loads(result.stdout)['status'] == 'unknown'


@pytest.mark.parametrize('created', ['invalid-private-marker', '2023-01-01T00:00:00', ''])
def test_malformed_lead_timestamp_is_unknown(tmp_path, created):
    db = tmp_path / 'synthetic.db'
    database(db, created=created)
    result = subprocess.run([sys.executable, str(TOOL), '--db', str(db),
                             '--max-pending-age-s', '600'],
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 2 and not result.stderr
    assert json.loads(result.stdout)['status'] == 'unknown'
    assert 'invalid-private-marker' not in result.stdout


def test_valid_past_timestamps_preserve_measured_ages(tmp_path):
    now = 1700000000.0
    db = tmp_path / 'synthetic.db'
    database(db, created=stamp(now - 12), heartbeat=now - 3)
    report = health.snapshot(db, now)
    assert report['oldest_pending_age_s'] == 12
    assert report['worker_heartbeat_age_s'] == 3


def add_pending(path, created):
    with sqlite3.connect(path) as db:
        db.execute('INSERT INTO leads VALUES(2, ?)', (created,))
        db.execute("INSERT INTO outbox VALUES(2, 'pending', 0)")


def test_mixed_timezone_offsets_compute_oldest_by_instant(tmp_path):
    now = 1700000000.0
    db = tmp_path / 'synthetic.db'
    # The lexicographically smaller value is recent despite representing a later instant.
    recent = datetime.fromtimestamp(now - 10, timezone(timedelta(hours=-12))).isoformat()
    old = datetime.fromtimestamp(now - 7200, timezone(timedelta(hours=14))).isoformat()
    assert recent < old
    database(db, created=recent)
    add_pending(db, old)
    assert health.snapshot(db, now)['oldest_pending_age_s'] == 7200


@pytest.mark.parametrize('invalid', ['future', 'zzz-private-invalid'])
def test_each_pending_timestamp_must_be_verifiable(tmp_path, invalid):
    now = 1700000000.0
    db = tmp_path / 'synthetic.db'
    database(db, created=stamp(now - 10))
    add_pending(db, stamp(now + 3600) if invalid == 'future' else invalid)
    with pytest.raises(ValueError):
        health.snapshot(db, now)


@pytest.mark.parametrize('invalid', ['future', 'zzz-private-invalid'])
def test_mixed_invalid_pending_cli_is_unknown(tmp_path, invalid):
    now = time.time()
    db = tmp_path / 'synthetic.db'
    database(db, created=stamp(now - 10), heartbeat=now)
    add_pending(db, stamp(now + 3600) if invalid == 'future' else invalid)
    result = subprocess.run([sys.executable, str(TOOL), '--db', str(db),
                             '--max-pending-age-s', '600', '--max-worker-idle-s', '5'],
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 2 and not result.stderr
    assert json.loads(result.stdout)['status'] == 'unknown'
    assert 'zzz-private-invalid' not in result.stdout and str(db) not in result.stdout


def test_mixed_timezone_backlog_cli_is_degraded(tmp_path):
    now = time.time()
    db = tmp_path / 'synthetic.db'
    recent = datetime.fromtimestamp(now - 10, timezone(timedelta(hours=-12))).isoformat()
    old = datetime.fromtimestamp(now - 7200, timezone(timedelta(hours=14))).isoformat()
    assert recent < old
    database(db, created=recent, heartbeat=now)
    add_pending(db, old)
    result = subprocess.run([sys.executable, str(TOOL), '--db', str(db),
                             '--max-pending-age-s', '600', '--max-worker-idle-s', '5'],
                            capture_output=True, text=True, timeout=10, check=False)
    report = json.loads(result.stdout)
    assert result.returncode == 1 and not result.stderr
    assert report['status'] == 'degraded' and report['oldest_pending_age_s'] >= 7200


@pytest.mark.parametrize('invalid', ['invalid-private-marker', 'nan', float('nan'),
                                     float('inf'), float('-inf')])
def test_invalid_pending_due_timestamp_cli_is_unknown(tmp_path, invalid):
    now = time.time()
    db = tmp_path / 'synthetic.db'
    database(db, created=stamp(now - 10), heartbeat=now)
    with sqlite3.connect(db) as connection:
        connection.execute('UPDATE outbox SET next_at=?', (invalid,))
    result = subprocess.run([sys.executable, str(TOOL), '--db', str(db),
                             '--max-pending-age-s', '600', '--max-worker-idle-s', '5'],
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 2 and not result.stderr
    assert json.loads(result.stdout)['status'] == 'unknown'
    assert 'invalid-private-marker' not in result.stdout and str(db) not in result.stdout


@pytest.mark.parametrize('next_at,due', [(-1.0, 1), (0, 1), (1700000000.0, 1),
                                          (1700000000.01, 0)])
def test_valid_pending_due_timestamp_counts(tmp_path, next_at, due):
    now = 1700000000.0
    db = tmp_path / 'synthetic.db'
    database(db, created=stamp(now - 10), heartbeat=now)
    with sqlite3.connect(db) as connection:
        connection.execute('UPDATE outbox SET next_at=?', (next_at,))
    assert health.snapshot(db, now)['due'] == due


@pytest.mark.parametrize('kind', ['pending', 'heartbeat'])
@pytest.mark.parametrize('age,expected', [(9.9996, 0), (10.0, 0), (10.0004, 1)])
def test_exact_threshold_uses_unrounded_age(tmp_path, monkeypatch, capsys, kind, age, expected):
    now = 1700000000.0
    db = tmp_path / 'synthetic.db'
    database(db, created=stamp(now - age) if kind == 'pending' else None,
             heartbeat=now - age if kind == 'heartbeat' else now)
    monkeypatch.setattr(health.time, 'time', lambda: now)
    code = health.main(['--db', str(db), '--max-pending-age-s', '10',
                        '--max-worker-idle-s', '10'])
    report = json.loads(capsys.readouterr().out)
    assert code == expected
    assert report['status'] == ('degraded' if expected else
                                'within_policy' if kind == 'pending' else 'idle_or_local_only')
