#!/usr/bin/env python3
"""Real-time, synthetic PBT API/outbox soak with immutable test budgets.

Never interpret these measurements as production traffic, live CRM, real-user
INP or unlimited reliability. No external network calls; all inputs are synthetic.
"""
import argparse
from collections import Counter
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import re
import os
from pathlib import Path
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / 'config' / 'runtime-soak-budgets.json'
SECRET = b'local-test-only-secret'


def percentile(values, p):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * p / 100) - 1)]


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class SyntheticCRM:
    """Deterministic at-least-once receiver; first attempts may fault."""
    def __init__(self):
        self.attempts = Counter()
        self.statuses = Counter()
        self.bad_signatures = 0
        self.bad_payloads = 0
        self.expected_crash_aborts = 0
        self.unexpected_transport_aborts = 0
        self.crash_window = False
        self.lock = threading.Lock()
        state = self

        class Handler(BaseHTTPRequestHandler):
            def reply(self, code):
                try:
                    self.send_response(code)
                    self.send_header('Content-Length', '2')
                    self.end_headers()
                    self.wfile.write(b'{}')
                except OSError:
                    pass  # The deliberately killed sender may have closed its socket.

            def do_POST(self):
                try:
                    length = int(self.headers.get('Content-Length') or 0)
                except ValueError:
                    length = -1
                if not 0 < length <= 8192:
                    with state.lock:
                        state.bad_payloads += 1
                        state.statuses[400] += 1
                    self.close_connection = True
                    self.reply(400)
                    return
                try:
                    body = self.rfile.read(length)
                except OSError:
                    body = b''
                if len(body) != length:
                    # An intentional SIGKILL may interrupt a request in-flight.
                    # Reject partial messages; never call these a bad HMAC.
                    with state.lock:
                        if state.crash_window:
                            state.expected_crash_aborts += 1
                        else:
                            state.unexpected_transport_aborts += 1
                        state.statuses[400] += 1
                    self.close_connection = True
                    self.reply(400)
                    return
                signature = self.headers.get('X-PBT-Signature', '')
                signature_ok = hmac.compare_digest(
                    signature, hmac.new(SECRET, body, hashlib.sha256).hexdigest())
                try:
                    lead_id = json.loads(body)['id']
                    payload_ok = type(lead_id) is int and lead_id > 0
                except (KeyError, TypeError, ValueError, UnicodeDecodeError):
                    lead_id, payload_ok = -1, False
                valid = signature_ok and payload_ok
                with state.lock:
                    if not signature_ok:
                        state.bad_signatures += 1
                        code, attempt = 403, 0
                    elif not payload_ok:
                        state.bad_payloads += 1
                        code, attempt = 422, 0
                    else:
                        state.attempts[lead_id] += 1
                        attempt = state.attempts[lead_id]
                        code = 200
                        if attempt == 1:
                            if lead_id % 97 == 0:
                                code = 200  # Intentionally too late for the 0.6s client deadline.
                            elif lead_id % 37 == 0:
                                code = 503
                            elif lead_id % 41 == 0:
                                code = 429
                            elif lead_id % 53 == 0:
                                code = 408
                    state.statuses[code] += 1
                if valid and attempt == 1 and lead_id % 97 == 0:
                    time.sleep(0.85)
                self.reply(code)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}/hook'
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def snapshot(self):
        with self.lock:
            return {'observed_distinct_leads': len(self.attempts),
                    'total_webhook_attempts': sum(self.attempts.values()),
                    'http_status_counts': {str(k): v for k, v in sorted(self.statuses.items())},
                    'invalid_hmac': self.bad_signatures,
                    'invalid_payloads': self.bad_payloads,
                    'expected_crash_aborts': self.expected_crash_aborts,
                    'unexpected_transport_aborts': self.unexpected_transport_aborts}

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=4)


def launch(env, port):
    proc = subprocess.Popen([sys.executable, str(ROOT / 'server' / 'app.py')],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    for _ in range(160):
        if proc.poll() is not None:
            raise RuntimeError('server_process_exited')
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health', timeout=.3) as resp:
                if resp.status == 200 and json.load(resp).get('ok') is True:
                    return proc
        except (OSError, ValueError, TimeoutError, urllib.error.HTTPError):
            time.sleep(.05)
    proc.kill()
    proc.wait(timeout=6)
    raise RuntimeError('server_not_ready')


def stop(proc):
    if proc and proc.poll() is None:
        proc.kill()
        proc.wait(timeout=6)


def lead(base, n):
    data = {
        'type': 'rent', 'subject': 'Синтетична тестова заявка',
        'method': 'phone', 'contact': '0671234567', 'hours': '16'
    }
    raw = json.dumps(data, ensure_ascii=False).encode()
    key = f'pbt-soak-{n:010d}'
    request = urllib.request.Request(
        base + '/api/lead', raw, {'Content-Type': 'application/json',
                                  'Origin': base, 'Idempotency-Key': key},
        method='POST')
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=6) as resp:
        status = resp.status
        payload = json.load(resp)
    duration_ms = (time.monotonic() - started) * 1000
    if status != 201 or payload.get('ok') is not True:
        raise RuntimeError('lead_contract_violation')
    return payload, duration_ms


def sqlite_counts(db):
    with sqlite3.connect(db, timeout=4) as conn:
        leads = conn.execute('SELECT count(*) FROM leads').fetchone()[0]
        status = dict(conn.execute('SELECT status, count(*) FROM outbox GROUP BY status').fetchall())
    return {'leads': leads, 'pending': status.get('pending', 0),
            'delivered': status.get('delivered', 0),
            'failed': status.get('failed', 0)}


def _proc_status(pid):
    status = Path(f'/proc/{pid}/status').read_text()
    rows = {}
    for line in status.splitlines():
        if line.startswith(('VmRSS:', 'Threads:', 'PPid:')):
            k, v = line.split(':', 1)
            rows[k] = int(v.split()[0])
    retudef _descendants(root_pid, proc_root=Path('/proc')):
    """Census process descendants, falling back to PPid on restricted procfs.

    A task/*/children file can be absent even for a live Linux task. If no
    children file is readable, inspect numeric /proc/*/status PPid records.
    Never silently certify an empty tree if the alternate census fails.
    """
    found = set()
    pending = [root_pid]
    child_interface_observed = False
    while pending:
        pid = pending.pop()
        try:
            tasks = (proc_root / str(pid) / 'task').iterdir()
            for task in tasks:
                try:
                    child_text = (task / 'children').read_text()
                    child_interface_observed = True
                except FileNotFoundError:
                    continue
                for token in child_text.split():
                    child = int(token)
                    if child != root_pid and child not in found:
                        found.add(child)
                        pending.append(child)
        except FileNotFoundError:
            continue
    if child_interface_observed:
        return found

    # Snapshot all process relationships before traversal: grandchildren may
    # appear ahead of their parents in the directory iteration order.
    by_parent = {}
    observed_root = False
    try:
        for entry in proc_root.iterdir():
            if not entry.name.isdecimal():
                continue
            try:
                status = (entry / 'status').read_text()
            except (FileNotFoundError, ProcessLookupError):
                continue  # Process disappeared during the snapshot.
            if int(entry.name) == root_pid:
                observed_root = True
            match = re.search(r'(?m)^PPid:\\s*(\\d+)\\s*$', status)
            if match is None:
                raise RuntimeError('proc_ppid_missing')
            by_parent.setdefault(int(match.group(1)), set()).add(int(entry.name))
    except OSError as exc:
        raise RuntimeError('proc_descendant_census_unavailable') from exc
    if not observed_root:
        raise RuntimeError('proc_root_not_observed')
    found = set()
    pending = [root_pid]
    while pending:
        pid = pending.pop()
        for child in by_parent.get(pid, ()):
            if child != root_pid and child not in found:
                found.add(child)
                pending.append(child)
    return found
urn found


def resources(proc):
    rows = _proc_status(proc.pid)
    if 'VmRSS' not in rows or 'Threads' not in rows:
        raise RuntimeError('rss_or_thread_measurement_missing')
    child_rss = 0
    live_children = 0
    for pid in _descendants(proc.pid):
        try:
            child = _proc_status(pid)
        except FileNotFoundError:
            continue  # Short-lived process exited between census and read.
        child_rss += child.get('VmRSS', 0)  # Zombies may not expose VmRSS.
        live_children += 1
    rows['ChildRSSSum'] = child_rss
    rows['ChildCount'] = live_children
    return rows


def backup(env):
    done = subprocess.run([sys.executable, str(ROOT / 'ops' / 'backup.py')],
                          cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, timeout=20, check=False)
    if done.returncode:
        raise RuntimeError('sqlite_backup_failed')


def exercise(profile, seconds, source_sha, cfg):
    periods = cfg[profile]
    limits = cfg['budgets']
    crm = SyntheticCRM()
    proc = None
    try:
        with tempfile.TemporaryDirectory(prefix='pbt-runtime-soak-') as temp:
            tmp = Path(temp)
            db = tmp / 'leads.db'
            backups = tmp / 'backups'
            port = free_port()
            base = f'http://127.0.0.1:{port}'
            env = {
                **os.environ, 'HOST': '127.0.0.1', 'PORT': str(port),
                'LEAD_DB': str(db), 'LEAD_WEBHOOK_URL': crm.url,
                'LEAD_WEBHOOK_SECRET': SECRET.decode(), 'TELEGRAM_BOT_TOKEN': '',
                'TELEGRAM_CHAT_ID': '', 'RATE_ANY_10MIN': '1000000',
                'RATE_LEAD_10MIN': '1000000', 'RATE_LEAD_DAY': '1000000',
                'DELIVERY_CONCURRENCY': '4', 'DELIVERY_TIMEOUT': '.6',
                'DELIVERY_POLL_S': '.05', 'DELIVERY_BACKOFF_S': '.05',
                'DELIVERY_MAX_ATTEMPTS': '4', 'MAX_CONNECTIONS': '48',
                'BACKUP_DIR': str(backups), 'BACKUP_KEEP': '6',
                'IP_HASH_SALT': 'local-test-only-ip-salt',
                'PYTHONDONTWRITEBYTECODE': '1',
            }
            proc = launch(env, port)
            began = time.monotonic()
            samples = []
            rss_epochs = [[]]
            child_rss_epochs = [[]]
            child_count_epochs = [[]]
            threads_max = 0
            pending_max = 0
            accepted = 0
            replayed = 0
            restarted = False
            checkpoints = set()
            last_resource_sample = -1
            while time.monotonic() - began < seconds:
                tick = time.monotonic()
                n = accepted + 1
                result, ms = lead(base, n)
                if result.get('ref') != f'PBT-{n:06d}':
                    raise RuntimeError('nonmonotonic_accepted_id')
                samples.append(ms)
                accepted += 1
                if accepted % 30 == 0:
                    again, _ = lead(base, n)
                    if again.get('ref') != result['ref'] or again.get('replayed') is not True:
                        raise RuntimeError('idempotent_replay_mismatch')
                    replayed += 1
                elapsed = time.monotonic() - began
                if last_resource_sample < 0 or elapsed - last_resource_sample >= 2:
                    seen = resources(proc)
                    rss_epochs[-1].append(seen['VmRSS'])
                    child_rss_epochs[-1].append(seen['ChildRSSSum'])
                    child_count_epochs[-1].append(seen['ChildCount'])
                    threads_max = max(threads_max, seen['Threads'])
                    pending_max = max(pending_max, sqlite_counts(db)['pending'])
                    last_resource_sample = elapsed
                for fraction, name in ((1 / 3, 'first'), (2 / 3, 'second')):
                    if elapsed >= seconds * fraction and name not in checkpoints:
                        backup(env)
                        checkpoints.add(name)
                if elapsed >= seconds / 2 and not restarted:
                    with crm.lock:
                        crm.crash_window = True
                    try:
                        stop(proc)
                        if sqlite_counts(db)['leads'] != accepted:
                            raise RuntimeError('accepted_lead_missing_after_process_crash')
                        proc = launch(env, port)
                    finally:
                        with crm.lock:
                            crm.crash_window = False
                    rss_epochs.append([])
                    child_rss_epochs.append([])
                    child_count_epochs.append([])
                    last_resource_sample = -1
                    restarted = True
                time.sleep(max(0, periods['request_period_s'] - (time.monotonic() - tick)))
            elapsed = time.monotonic() - began
            drain_until = time.monotonic() + limits['maximum_drain_s']
            state = sqlite_counts(db)
            while (state['delivered'] != accepted or state['pending'] != 0) and time.monotonic() < drain_until:
                time.sleep(.15)
                state = sqlite_counts(db)
            drain_elapsed = time.monotonic() - (drain_until - limits['maximum_drain_s'])
            with sqlite3.connect(db, timeout=5) as conn:
                integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
            actual_backups = sorted(backups.glob('leads-*.db'))
            for file in actual_backups:
                with sqlite3.connect(file, timeout=5) as conn:
                    if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise RuntimeError('backup_integrity_invalid')
            stats = crm.snapshot()
            rss_peaks = [max(x) for x in rss_epochs if x]
            rss_growth = [max(x) - x[0] for x in rss_epochs if x]
            tree_rss_peak = max(
                server + child
                for server_epoch, child_epoch in zip(rss_epochs, child_rss_epochs)
                for server, child in zip(server_epoch, child_epoch))
            child_count_peak = max(max(group) for group in child_count_epochs if group)
            report = {
                'schema': 'pbt-soak-evidence-v1',
                'source_sha': source_sha,
                'profile': profile,
                'scope': 'synthetic_local_http_sqlite_not_production',
                'minimum_required_duration_s': periods['minimum_duration_s'],
                'observed_duration_s': round(elapsed, 3),
                'accepted_leads': accepted,
                'minimum_required_accepted': periods['minimum_accepted'],
                'idempotent_replays': replayed,
                'api_p50_ms': round(percentile(samples, 50), 3),
                'api_p95_ms': round(percentile(samples, 95), 3),
                'api_p99_ms': round(percentile(samples, 99), 3),
                'api_max_ms': round(max(samples), 3),
                'api_latency_samples_ms': [round(v, 3) for v in samples],
                'rss_sample_epochs_kib': rss_epochs,
                'child_rss_sample_epochs_kib': child_rss_epochs,
                'child_process_sample_epochs': child_count_epochs,
                'tree_vm_rss_sum_peak_kib': tree_rss_peak,
                'observed_child_processes_peak': child_count_peak,
                'resource_scope': 'sampled_server_plus_descendants_sum_vm_rss_not_cgroup_peak',
                'rss_peak_kib': max(rss_peaks),
                'rss_growth_max_kib': max(rss_growth),
                'threads_peak': threads_max,
                'pending_outbox_peak': pending_max,
                'process_crash_and_restart': restarted,
                'backup_checkpoints': len(actual_backups),
                'outbox': state,
                'final_sqlite_integrity': integrity,
                'drain_elapsed_s': round(drain_elapsed, 3),
                'crm': stats,
                'limits': limits,
                'worker_liveness_scope': 'process_alive_and_backlog_drained_only',
                'field_inp': 'NOT_MEASURED',
            }
            violations = []
            def gate(ok, name):
                if not ok:
                    violations.append(name)
            gate(elapsed >= periods['minimum_duration_s'], 'insufficient_duration')
            gate(accepted >= periods['minimum_accepted'], 'insufficient_request_volume')
            gate(report['api_p99_ms'] <= limits['maximum_p99_lead_ms'], 'api_p99')
            gate(report['rss_peak_kib'] <= limits['maximum_rss_kib'], 'rss_peak')
            gate(report['rss_growth_max_kib'] <= limits['maximum_rss_growth_kib_per_process'], 'rss_growth')
            gate(tree_rss_peak <= limits['maximum_tree_vm_rss_sum_kib'], 'tree_rss_peak')
            gate(child_count_peak <= limits['maximum_delivery_descendants'], 'delivery_descendant_bound')
            if profile == 'soak':
                gate(child_count_peak >= 1, 'no_outbound_child_observed')
            gate(threads_max <= limits['maximum_thread_count'], 'thread_bound')
            gate(pending_max <= limits['maximum_pending_outbox'], 'outbox_backlog_peak')
            gate(drain_elapsed <= limits['maximum_drain_s'], 'outbox_drain_deadline')
            gate(state == {'leads': accepted, 'pending': 0, 'delivered': accepted, 'failed': 0},
                 'accepted_lead_outbox_invariant')
            gate(integrity == 'ok', 'sqlite_integrity')
            gate(restarted, 'restart_not_executed')
            gate(len(actual_backups) >= limits['minimum_backup_checkpoints'], 'backup_checkpoint_missing')
            gate(stats['invalid_hmac'] == 0, 'hmac_failed')
            gate(stats['invalid_payloads'] == 0, 'webhook_payload_invalid')
            gate(stats['unexpected_transport_aborts'] == 0, 'unexpected_transport_abort')
            # Exactly four delivery worker slots exist in this synthetic profile.
            gate(stats['expected_crash_aborts'] <= int(env['DELIVERY_CONCURRENCY']),
                 'crash_transport_abort_bound')
            gate(stats['observed_distinct_leads'] == accepted, 'webhook_coverage')
            if profile == 'soak':
                gate(all(stats['http_status_counts'].get(str(code), 0) > 0 for code in (408, 429, 503)),
                     'required_fault_class_not_observed')
                gate(stats['total_webhook_attempts'] > accepted, 'retry_path_not_exercised')
            report['violations'] = violations
            report['status'] = 'PASS' if not violations else 'FAIL'
            return report
    finally:
        stop(proc)
        crm.stop()


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--profile', choices=('smoke', 'soak'), required=True)
    p.add_argument('--duration-s', type=float, required=True)
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args(argv)
    cfg = json.loads(CONFIG.read_text())
    minimum = cfg[args.profile]['minimum_duration_s']
    if not math.isfinite(args.duration_s) or args.duration_s < minimum:
        print('FAIL: duration below locked test budget', file=sys.stderr)
        return 2
    actual_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    expected_sha = os.environ.get('PBT_HEAD_SHA')
    if expected_sha and expected_sha != actual_sha:
        print('FAIL: HEAD provenance mismatch', file=sys.stderr)
        return 2
    try:
        evidence = exercise(args.profile, args.duration_s, actual_sha, cfg)
    except Exception as exc:  # noqa: BLE001
        evidence = {'schema': 'pbt-soak-evidence-v1', 'source_sha': actual_sha,
                    'profile': args.profile, 'status': 'FAIL',
                    'violations': ['uncaught_' + type(exc).__name__],
                    'scope': 'synthetic_local_http_sqlite_not_production',
                    'limits': cfg['budgets']}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(evidence, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(f"soak {evidence['status']}: {args.report}, violations={evidence['violations']}")
    return 0 if evidence['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
