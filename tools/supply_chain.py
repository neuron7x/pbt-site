#!/usr/bin/env python3
"""ADV-06/EVD-01/NET-07: source, toolchain and dependency provenance, and a CycloneDX-shaped SBOM.

  capture --expected-head SHA --out artifacts/provenance.json   require a clean checkout of SHA
  verify  artifacts/provenance.json --expected-head SHA         reject stale or modified source
  sbom    --out sbom.json                    every locked requirement with its hashes

This is SLSA-aligned recording, not a SLSA build level: nothing here is signed by the build platform,
and GitHub artifact attestations are unavailable to this private repository's plan. The identity of the
runner is whatever GitHub's environment states; authenticity rests on the provider API, as elsewhere.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parent.parent
FULL_SHA = re.compile(r'.+@[0-9a-f]{40}\Z')
REQ = re.compile(
    r'^([A-Za-z0-9_.\-\[\]]+)==([^\s\\]+)[ \t]*\\*[ \t]*\n'
    r'((?:[ \t]+--hash=sha256:[0-9a-f]{64}[ \t]*\\*[ \t]*(?:\n|$))+)', re.M)
LOCKS = ('requirements.txt', 'requirements-sast.txt')


class Rejected(ValueError):
    pass


def git(root, *args):
    return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True, text=True, timeout=20).stdout.strip()


def workflow_files(root):
    folder = root / '.github' / 'workflows'
    return sorted([*folder.glob('*.yml'), *folder.glob('*.yaml')])


def require_clean_checkout(root):
    # HEAD alone does not identify staged, modified or untracked source bytes.
    entries = git(root, 'ls-files', '-v', '-z').split('\0')
    if any(entry and (entry[0].islower() or entry[0] == 'S') for entry in entries):
        raise Rejected('hidden_index_flags')
    if git(root, 'status', '--porcelain=v1', '--untracked-files=normal'):
        raise Rejected('dirty_checkout')


def workflow_uses(path):
    """Inspect YAML nodes without constructing objects or expanding alias graphs."""
    try:
        document = yaml.compose(path.read_text(encoding='utf-8'), Loader=yaml.SafeLoader)
    except (yaml.YAMLError, RecursionError) as exc:
        raise Rejected(f'workflow_yaml_invalid_{path.name}') from exc
    if not isinstance(document, yaml.MappingNode):
        raise Rejected(f'workflow_mapping_required_{path.name}')
    pending, seen = [document], set()
    while pending:
        node = pending.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        if isinstance(node, yaml.MappingNode):
            keys = set()
            for key, value in node.value:
                if not isinstance(key, yaml.ScalarNode) or key.value in keys:
                    raise Rejected(f'workflow_ambiguous_key_{path.name}')
                keys.add(key.value)
                if key.value == 'uses':
                    if not isinstance(value, yaml.ScalarNode) or value.tag != 'tag:yaml.org,2002:str':
                        raise Rejected(f'workflow_action_invalid_{path.name}')
                    yield value.value
                pending.append(value)
        elif isinstance(node, yaml.SequenceNode):
            pending.extend(node.value)


def action_pins(root):
    pins = {}
    for path in workflow_files(root):
        for use in workflow_uses(path):
            if use.startswith('./'):
                continue
            if not FULL_SHA.fullmatch(use):
                raise Rejected(f'unpinned_action_{path.name}_{use}')
            pins.setdefault(use, []).append(path.name)
    if not pins:
        raise Rejected('no_workflows_scanned')
    return {k: sorted(set(v)) for k, v in sorted(pins.items())}


def locked_requirements(path):
    return parse_locked_requirements(path.read_text(encoding='utf-8'), path.name)


def parse_locked_requirements(raw, lock_name):
    """Parse lock text from either a checkout or an immutable Git blob."""
    entries = REQ.findall(raw)
    names = re.findall(r'^([A-Za-z0-9_.\-\[\]]+)==', raw, re.M)
    if not names:
        raise Rejected(f'empty_lock_{lock_name}')
    if len(entries) != len(names):
        raise Rejected(f'requirement_without_hash_{lock_name}')
    if re.search(r'^[A-Za-z0-9_.\-\[\]]+\s*(?:>=|<=|~=|>|<|!=)', raw, re.M):
        raise Rejected(f'unpinned_requirement_{lock_name}')
    remainder = REQ.sub('', raw)
    if any(line.strip() and not line.lstrip().startswith('#') for line in remainder.splitlines()):
        raise Rejected(f'unparsed_lock_content_{lock_name}')
    return [{'name': n.lower(), 'version': v, 'hashes': sorted(re.findall(r'sha256:([0-9a-f]{64})', h))} for n, v, h in entries]


def derive(root):
    locks = {}
    for name in LOCKS:
        path = root / name
        if not path.exists():
            raise Rejected(f'missing_lock_{name}')
        locked_requirements(path)
        locks[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    pins = action_pins(root)
    workflows = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in workflow_files(root)}
    return {'head_sha': git(root, 'rev-parse', 'HEAD'), 'tree_sha': git(root, 'rev-parse', 'HEAD^{tree}'),
            'locks_sha256': locks, 'action_pins': pins,
            'workflows_sha256': hashlib.sha256(json.dumps(workflows, sort_keys=True).encode()).hexdigest()}


def capture(root, expected_head, env=os.environ):
    identity = derive(root)
    if identity['head_sha'] != expected_head:
        raise Rejected('checkout_differs_from_expected_head')
    claimed = env.get('PBT_HEAD_SHA')
    if claimed and claimed != expected_head:
        raise Rejected('pbt_head_sha_differs')
    require_clean_checkout(root)
    return {'schema': 'pbt-provenance-v1', **identity, 'event_sha': env.get('GITHUB_SHA'),
            'event': env.get('GITHUB_EVENT_NAME'), 'run_id': env.get('GITHUB_RUN_ID'),
            'run_attempt': env.get('GITHUB_RUN_ATTEMPT'), 'repository': env.get('GITHUB_REPOSITORY'),
            'python': platform.python_version(), 'kernel': platform.release(), 'machine': platform.machine(),
            'slsa_level': 'none_claimed', 'signed': False}


def verify(root, receipt, expected_head):
    if receipt.get('schema') != 'pbt-provenance-v1':
        raise Rejected('schema')
    now = derive(root)
    if expected_head != now['head_sha'] or receipt.get('head_sha') != expected_head:
        raise Rejected('stale_source_revision')
    for key in ('tree_sha', 'locks_sha256', 'action_pins', 'workflows_sha256'):
        if receipt.get(key) != now[key]:
            raise Rejected(f'receipt_drift_{key}')
    require_clean_checkout(root)
    return {'status': 'PASS', 'head_sha': expected_head}


def validate_sbom_contract(bom):
    """Bounded CycloneDX 1.5 component checks; not a full external JSON Schema validation."""
    if bom.get('bomFormat') != 'CycloneDX' or bom.get('specVersion') != '1.5':
        raise Rejected('sbom_format_or_version_invalid')
    components = bom.get('components')
    if not isinstance(components, list) or not components:
        raise Rejected('sbom_components_missing')
    refs = set()
    for component in components:
        if not isinstance(component, dict) or component.get('scope') not in ('required', 'optional', 'excluded'):
            raise Rejected('invalid_component_scope')
        ref = component.get('bom-ref')
        if not isinstance(ref, str) or not ref or ref in refs:
            raise Rejected('duplicate_or_missing_sbom_ref')
        refs.add(ref)
        origin = component.get('properties')
        if (not isinstance(origin, list) or len(origin) != 1 or not isinstance(origin[0], dict)
                or set(origin[0]) != {'name', 'value'}
                or origin[0]['name'] != 'pbt:source-lockfile'
                or origin[0]['value'] not in LOCKS):
            raise Rejected('invalid_component_lock_origin')
        hashes = component.get('hashes')
        if (not isinstance(hashes, list) or not hashes
                or any(not isinstance(h, dict) or h.get('alg') != 'SHA-256'
                       or not isinstance(h.get('content'), str)
                       or not re.fullmatch(r'[0-9a-f]{64}', h['content']) for h in hashes)):
            raise Rejected('invalid_component_hashes')
    return len(components)


def sbom(root):
    # CI/test/security locks are required for evidence generation; the deployed server is stdlib-only.
    components = []
    for name in LOCKS:
        for item in locked_requirements(root / name):
            components.append({'type': 'library', 'name': item['name'], 'version': item['version'],
                               'bom-ref': f"{name}::{item['name']}@{item['version']}",
                               'purl': f"pkg:pypi/{item['name']}@{item['version']}",
                               'scope': 'required',
                               'properties': [{'name': 'pbt:source-lockfile', 'value': name}],
                               'hashes': [{'alg': 'SHA-256', 'content': h} for h in item['hashes']]})
    report = {'bomFormat': 'CycloneDX', 'specVersion': '1.5', 'components': components,
              'metadata': {'component': {'type': 'application', 'name': 'pbt-site', 'version': git(root, 'rev-parse', 'HEAD')}}}
    validate_sbom_contract(report)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='command', required=True)
    c = sub.add_parser('capture'); c.add_argument('--expected-head', required=True); c.add_argument('--out', type=Path, required=True)
    v = sub.add_parser('verify'); v.add_argument('receipt', type=Path); v.add_argument('--expected-head', required=True)
    s = sub.add_parser('sbom'); s.add_argument('--out', type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if a.command == 'capture':
            result = capture(ROOT, a.expected_head)
        elif a.command == 'verify':
            print(json.dumps(verify(ROOT, json.loads(a.receipt.read_text(encoding='utf-8')), a.expected_head)))
            return 0
        else:
            result = sbom(ROOT)
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(result, indent=1, sort_keys=True) + '\n', encoding='utf-8')
        print(json.dumps({'status': 'PASS', 'written': str(a.out)}))
        return 0
    except (Rejected, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'FAIL', 'reason': str(exc)[:150], 'error_type': type(exc).__name__}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
