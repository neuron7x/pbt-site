#!/usr/bin/env python3
"""Narrow stdlib AST static gate for PBT server and operational Python entrypoints.

This supplements (does not replace) vulnerability scanning or human threat review.
"""
import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
DENIED_CALLS = {
    'eval', 'exec', 'os.system', 'os.popen',
    'pickle.load', 'pickle.loads', 'marshal.load', 'marshal.loads',
}
HTTP_CALLS = {'urllib.request.urlopen', 'urlopen', 'requests.get', 'requests.post'}


def qualified(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = qualified(node.value)
        return prefix + '.' + node.attr if prefix else node.attr
    return ''


def scan_source(content, name):
    try:
        tree = ast.parse(content, filename=name)
    except (SyntaxError, ValueError):
        return [{'file': name, 'line': 0, 'rule': 'unparseable_python'}]
    findings = []
    # urllib.request.build_opener().open(...) is an outbound HTTP path too.
    # Without this dataflow edge the bounded transport child would bypass
    # the explicit-timeout static rule merely by using a custom opener.
    opener_names = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                and qualified(node.value.func) in ('urllib.request.build_opener', 'build_opener')):
            opener_names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call = qualified(node.func)
        rule = None
        if call in DENIED_CALLS:
            rule = 'dangerous_dynamic_or_deserialization_call'
        elif call.startswith('subprocess.') and any(
                keyword.arg == 'shell' and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True for keyword in node.keywords):
            rule = 'shell_execution'
        elif (call in HTTP_CALLS or call in {name + '.open' for name in opener_names}) and not any(
                kw.arg == 'timeout' for kw in node.keywords):
            rule = 'network_without_timeout'
        if rule:
            findings.append({'file': name, 'line': node.lineno, 'rule': rule})
    return findings


def run(roots):
    files = []
    for root in roots:
        base = ROOT / root
        if not base.is_dir():
            raise OSError('missing_scanned_root')
        files += sorted(base.rglob('*.py'))
    if not files:
        raise OSError('no_source_files_scanned')
    results = []
    for path in files:
        name = path.relative_to(ROOT).as_posix()
        results.extend(scan_source(path.read_text(encoding='utf-8'), name))
    return {'files_scanned': len(files), 'findings': results}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--roots', nargs='+', default=['server', 'ops'])
    p.add_argument('--expected-head', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(argv)
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    evidence = {
        'schema': 'pbt-scoped-static-guard-v1',
        'head_sha': actual, 'scanned_roots': args.roots,
        'scope': 'AST primitive guard; not full SAST, ASVS certification or production review',
        'status': 'FAIL', 'files_scanned': 0, 'findings': [],
    }
    try:
        if actual != args.expected_head:
            raise ValueError('SHA mismatch')
        if sorted(args.roots) != ['ops', 'server']:
            raise ValueError('scanned roots modified')
        evidence.update(run(args.roots))
        if not evidence['findings']:
            evidence['status'] = 'PASS'
    except (OSError, UnicodeError, ValueError) as exc:
        evidence['findings'].append({'file': 'scanner', 'line': 0, 'rule': type(exc).__name__})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print('static-guard', evidence['status'], 'files=', evidence['files_scanned'],
          'findings=', len(evidence['findings']))
    return 0 if evidence['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
