#!/usr/bin/env python3
"""Narrow stdlib AST static gate for PBT server and operational Python entrypoints.

This supplements (does not replace) vulnerability scanning or human threat review.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
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


def committed_sources(head, files, roots):
    """Bind the scanned snapshot to Git, independently of index visibility flags."""
    if not re.fullmatch(r'[0-9a-f]{40}', head):
        raise ValueError('invalid_source_sha')
    listing = subprocess.run(
        ['git', '--no-replace-objects', 'ls-tree', '-rz', '--full-tree', head, '--', *roots],
        cwd=ROOT, check=True, capture_output=True, timeout=15).stdout
    expected = {}
    for record in listing.split(b'\0'):
        if not record:
            continue
        metadata, raw_name = record.split(b'\t', 1)
        name = raw_name.decode('utf-8')
        mode, kind, blob = metadata.decode('ascii').split()
        if kind != 'blob' or mode not in ('100644', '100755'):
            raise ValueError('unsupported_source_entry')
        if not name.endswith('.py'):
            continue
        expected[name] = blob
    actual = {path.relative_to(ROOT).as_posix() for path in files}
    if not expected or actual != set(expected):
        raise ValueError('source_inventory_mismatch')
    snapshots, records = [], []
    for name in sorted(expected):
        path = ROOT / name
        if path.resolve() != path.absolute():
            raise ValueError('source_path_alias')
        raw = path.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw,
                            usedforsecurity=False).hexdigest()
        if blob != expected[name]:
            raise ValueError('source_blob_mismatch')
        snapshots.append((name, raw.decode('utf-8')))
        records.append({'path': name, 'git_blob_sha': blob,
                        'sha256': hashlib.sha256(raw).hexdigest()})
    return snapshots, records


def run(roots, expected_head=None):
    files = []
    for root in roots:
        base = ROOT / root
        if not base.is_dir():
            raise OSError('missing_scanned_root')
        if base.resolve() != base.absolute():
            raise ValueError('source_path_alias')
        # rglob does not descend directory symlinks. Reject them explicitly so an
        # importable subtree cannot disappear from both Python file inventories.
        entries = sorted(base.rglob('*'))
        if any(path.is_symlink() for path in entries):
            raise ValueError('source_path_alias')
        files += [path for path in entries if path.suffix == '.py']
    if not files:
        raise OSError('no_source_files_scanned')
    if expected_head is None:
        snapshots = [(path.relative_to(ROOT).as_posix(), path.read_text(encoding='utf-8'))
                     for path in files]
        records = None
    else:
        snapshots, records = committed_sources(expected_head, files, roots)
    results = []
    for name, content in snapshots:
        results.extend(scan_source(content, name))
    report = {'files_scanned': len(snapshots), 'findings': results}
    if records is not None:
        report['source_files'] = records
    return report


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--roots', nargs='+', default=['server', 'ops'])
    p.add_argument('--expected-head', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(argv)
    actual = subprocess.check_output(['git', '--no-replace-objects', 'rev-parse', 'HEAD'],
                                     cwd=ROOT, text=True).strip()
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
        evidence.update(run(args.roots, expected_head=actual))
        if not evidence['findings']:
            evidence['status'] = 'PASS'
    except (OSError, UnicodeError, ValueError, subprocess.SubprocessError) as exc:
        evidence['findings'].append({'file': 'scanner', 'line': 0, 'rule': type(exc).__name__})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print('static-guard', evidence['status'], 'files=', evidence['files_scanned'],
          'findings=', len(evidence['findings']))
    return 0 if evidence['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
