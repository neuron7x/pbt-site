#!/usr/bin/env python3
"""ADV-02: apply each catalogued fault to a disposable copy of the tree and require its oracle to fail.

Never touches the working tree. A positive control runs first: an oracle already failing on clean code
proves nothing. An edit that does not apply exactly is an error, not a kill; so is a collection failure.
Verdicts: KILLED, SURVIVED, INVALID. A mutant expected UNTESTABLE records why instead of being hidden.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
IGNORE = shutil.ignore_patterns('.git', 'data', 'dist', 'artifacts', '__pycache__', '*.pyc', '.pytest_cache', 'node_modules')
ENV_DROP = ('PYTEST_ADDOPTS',)


def run_oracle(tree, oracle, timeout):
    env = {k: v for k, v in os.environ.items() if k not in ENV_DROP}
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    command = oracle if isinstance(oracle, list) and oracle and oracle[0] == 'node' else \
        [sys.executable, '-m', 'pytest', '-q', '-x', '-p', 'no:cacheprovider', '--tb=line', *oracle]
    try:
        r = subprocess.run(command, cwd=tree, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 'TIMEOUT', ''
    tail = '\n'.join((r.stdout + r.stderr).strip().splitlines()[-4:])[:600]
    return r.returncode, tail


def apply_edits(tree, edits):
    for edit in edits:
        path = tree / edit['file']
        text = path.read_text(encoding='utf-8')
        if text.count(edit['find']) != 1:
            return f"edit_does_not_apply_exactly:{edit['file']}:{text.count(edit['find'])}"
        path.write_text(text.replace(edit['find'], edit['replace']), encoding='utf-8')
    return None


def execute(mutant, tree, timeout):
    if mutant.get('expected') == 'UNTESTABLE':
        return {'id': mutant['id'], 'verdict': 'UNTESTABLE', 'reason': mutant['reason']}
    saved = {e['file']: (tree / e['file']).read_bytes() for e in mutant['edits']}
    started = time.monotonic()
    try:
        problem = apply_edits(tree, mutant['edits'])
        if problem:
            return {'id': mutant['id'], 'verdict': 'INVALID', 'reason': problem}
        code, tail = run_oracle(tree, mutant['oracle'], timeout)
    finally:
        for name, raw in saved.items():
            (tree / name).write_bytes(raw)
    # pytest: 1 = tests failed (a kill), 0 = survived, anything else = the oracle did not run.
    node = mutant['oracle'][0] == 'node'
    if code == 0:
        verdict = 'SURVIVED'
    elif code == 1 or code == 'TIMEOUT' or (node and code):
        verdict = 'KILLED'
    else:
        verdict = 'INVALID'
    return {'id': mutant['id'], 'verdict': verdict, 'oracle_exit': code, 'seconds': round(time.monotonic() - started, 1),
            'evidence': tail if verdict != 'KILLED' else tail[-240:]}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--catalog', type=Path, default=ROOT / 'config/mutation-catalog.json')
    p.add_argument('--out', type=Path, default=None)
    p.add_argument('--jobs', type=int, default=3)
    p.add_argument('--timeout', type=int, default=240)
    p.add_argument('--only', nargs='*', default=None)
    a = p.parse_args(argv)
    catalog = json.loads(a.catalog.read_text(encoding='utf-8'))
    mutants = [m for m in catalog['mutants'] if not a.only or m['id'] in a.only]
    live = [m for m in mutants if m.get('expected') != 'UNTESTABLE']
    with tempfile.TemporaryDirectory(prefix='pbt-mutation-') as scratch:
        trees = []
        for i in range(max(a.jobs, 1)):
            tree = Path(scratch) / f'w{i}'
            shutil.copytree(ROOT, tree, ignore=IGNORE)
            trees.append(tree)
        oracles = sorted({' '.join(m['oracle']) for m in live if m['oracle'][0] != 'node'})
        selection = sorted({arg for m in live if m['oracle'][0] != 'node' for arg in m['oracle']})
        control, tail = run_oracle(trees[0], selection, a.timeout * 4) if selection else (0, '')
        if control != 0:
            print(json.dumps({'status': 'FAIL', 'reason': 'positive_control_failed', 'exit': control, 'tail': tail}))
            return 1
        free = list(trees)

        def worker(mutant):
            tree = free.pop()
            try:
                return execute(mutant, tree, a.timeout)
            finally:
                free.append(tree)
        with ThreadPoolExecutor(max_workers=max(a.jobs, 1)) as pool:
            results = list(pool.map(worker, mutants))
    counts = {}
    for r in results:
        counts[r['verdict']] = counts.get(r['verdict'], 0) + 1
    bad = [r['id'] for r in results if r['verdict'] in ('SURVIVED', 'INVALID')]
    report = {'schema': 'pbt-mutation-ledger-v1', 'status': 'FAIL' if bad else 'PASS', 'counts': counts, 'failed_ids': bad,
              'catalog_sha256': hashlib.sha256(a.catalog.read_bytes()).hexdigest(), 'positive_control_oracles': len(oracles),
              'score_note': 'Designated critical faults only: no claim about any other fault.',
              'head_sha': os.environ.get('PBT_HEAD_SHA') or subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
              'results': results}
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(report, indent=1, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('status', 'counts', 'failed_ids')}, ensure_ascii=False))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
