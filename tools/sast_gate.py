#!/usr/bin/env python3
"""NET-07: run the pinned broad scanner over declared roots; a scanner that did not scan cannot pass.

Complements, never replaces, tools/security_static.py. Every waiver names its finding and a rationale;
a stale waiver also fails, so the list cannot rot into blanket suppression. No ASVS claim follows from this.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
ROOTS = ['server', 'ops', 'tools']
SCANNER = [sys.executable, '-m', 'bandit', '-r', *ROOTS, '-f', 'json', '-q', '--severity-level', 'medium']


def fingerprint(finding):
    """Test, file and the flagged statement only: bandit's context lines carry numbers that shift with any edit."""
    prefix = f"{finding['line_number']} "
    lines = [ln[len(prefix):] for ln in finding['code'].splitlines() if ln.startswith(prefix)] or [finding['code']]
    return hashlib.sha256(f"{finding['test_id']}\0{finding['filename']}\0{' '.join(lines[0].split())}".encode()).hexdigest()[:20]


def evaluate(stdout, returncode, waivers, min_files):
    """bandit: 0 clean, 1 findings; anything else, or a report that scanned nothing, is not a result."""
    if returncode not in (0, 1):
        return {'status': 'FAIL', 'reason': f'scanner_exit_{returncode}'}
    try:
        report = json.loads(stdout)
        results = report['results']
        totals = report['metrics']['_totals']
        scanned = [k for k in report['metrics'] if k != '_totals']
    except (ValueError, KeyError, TypeError):
        return {'status': 'FAIL', 'reason': 'scanner_output_unparsable'}
    if report.get('errors'):
        return {'status': 'FAIL', 'reason': 'scanner_reported_errors', 'errors': len(report['errors'])}
    if len(scanned) < min_files or totals.get('loc', 0) <= 0:
        return {'status': 'FAIL', 'reason': 'scanner_scanned_too_little', 'files': len(scanned)}
    allowed = {w['fingerprint']: w for w in waivers}
    if any(not str(w.get('rationale', '')).strip() for w in waivers):
        return {'status': 'FAIL', 'reason': 'waiver_without_rationale'}
    seen = {fingerprint(r): r for r in results}
    open_findings = [{'id': k, 'test': r['test_id'], 'file': r['filename'], 'line': r['line_number'], 'severity': r['issue_severity']}
                     for k, r in seen.items() if k not in allowed]
    stale = sorted(k for k in allowed if k not in seen)
    status = 'PASS' if not open_findings and not stale else 'FAIL'
    return {'status': status, 'files_scanned': len(scanned), 'loc': totals['loc'], 'findings': len(results),
            'waived': len(results) - len(open_findings), 'open': open_findings, 'stale_waivers': stale,
            'scope': 'bandit severity>=medium on server+ops+tools; low-severity findings are not gated; not ASVS, not DAST, no JS coverage (see tools/dom_sinks.py)'}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--waivers', type=Path, default=ROOT / 'config/sast-waivers.json')
    p.add_argument('--min-files', type=int, default=20)
    p.add_argument('--out', type=Path, default=None)
    p.add_argument('--list', action='store_true', help='print findings for waiver review')
    a = p.parse_args(argv)
    try:
        run = subprocess.run(SCANNER, cwd=ROOT, capture_output=True, text=True, timeout=300)
        waivers = json.loads(a.waivers.read_text(encoding='utf-8'))['waivers']
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'FAIL', 'reason': type(exc).__name__}))
        return 1
    if a.list:
        for r in json.loads(run.stdout)['results']:
            print(fingerprint(r), r['test_id'], r['issue_severity'], f"{r['filename']}:{r['line_number']}", ' '.join(r['issue_text'].split())[:70])
        return 0
    result = evaluate(run.stdout, run.returncode, waivers, a.min_files)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(result, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
