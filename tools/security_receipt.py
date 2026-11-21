#!/usr/bin/env python3
"""Зберегти результат OSV й перевірити повноту переліку залежностей.

Цей звіт не підтверджує відсутність невідомих вразливостей. OSV з
--disable-pip перевіряє наявність хешів, але не байти дистрибутивів;
байтову перевірку виконує окреме встановлення у release workflow.
"""
import argparse
import base64
import binascii
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import re
import subprocess

from packaging.version import Version

ACTION_COMMIT = '1220774d901786e6f652ae159f7b6bc8fea6d266'
SHA = re.compile(r'[0-9a-f]{40}')
PIN = re.compile(r'^([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.!+_-]*)\s*\\?\s*$')
HASH = re.compile(r'^\s*--hash=sha256:[0-9a-f]{64}\s*\\{0,2}\s*$')


def canonical(name):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9]|[A-Za-z0-9]', name):
        raise ValueError('invalid_dependency_name')
    return re.sub(r'[-_.]+', '-', name).lower()


def required_packages(source):
    """Підтримуємо лише явні exact pins і sha256 hashes; інакше fail-closed."""
    result = {}
    current = None
    hashes = 0
    for line in source.decode('utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        pin = PIN.fullmatch(line)
        if pin:
            if current is not None and not hashes:
                raise ValueError('requirement_missing_hash')
            name = canonical(pin.group(1))
            if name in result:
                raise ValueError('duplicate_requirement')
            result[name] = Version(pin.group(2))
            current, hashes = name, 0
        elif HASH.fullmatch(line) and current is not None:
            hashes += 1
        else:
            raise ValueError('unsupported_requirements_format')
    if not result or not hashes:
        raise ValueError('requirement_missing_hash')
    return result


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate_json_key')
        result[key] = value
    return result


def _reject_json_constant(_value):
    raise ValueError('invalid_json_constant')


def verify_source_provenance(head, source, requirements):
    """Порівняти checkout, шлях і байти з blob саме в заявленому коміті."""
    if not SHA.fullmatch(head):
        raise ValueError('invalid_head_sha')

    def git(*args):
        try:
            return subprocess.run(['git', *args], check=True, capture_output=True,
                                  timeout=15).stdout
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise ValueError('git_provenance_unavailable') from exc

    try:
        actual_head = git('rev-parse', '--verify', 'HEAD').decode('ascii').strip()
        root = Path(os.fsdecode(git('rev-parse', '--show-toplevel').strip())).resolve()
    except UnicodeError as exc:
        raise ValueError('git_provenance_unavailable') from exc
    if actual_head != head:
        raise ValueError('git_head_mismatch')
    try:
        relative = requirements.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError('requirements_path_mismatch') from exc
    if relative not in ('requirements.txt', 'requirements-sast.txt'):
        raise ValueError('requirements_path_mismatch')
    if git('cat-file', 'blob', f'{head}:{relative}') != source:
        raise ValueError('requirements_blob_mismatch')


def verify_report(text, expected):
    try:
        data = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError('invalid_scanner_json') from exc
    if not isinstance(data, dict) or set(data) != {'dependencies', 'fixes'}:
        raise ValueError('invalid_scanner_schema')
    if not isinstance(data['dependencies'], list) or not data['dependencies']:
        raise ValueError('missing_scanner_dependencies')
    if data['fixes'] != []:
        raise ValueError('unexpected_scanner_fixes')
    scanned = {}
    for dep in data['dependencies']:
        if not isinstance(dep, dict) or 'skip_reason' in dep:
            raise ValueError('scanner_skipped_dependency')
        if (not isinstance(dep.get('name'), str) or not isinstance(dep.get('version'), str)
                or not isinstance(dep.get('vulns'), list)):
            raise ValueError('invalid_dependency_schema')
        if dep['vulns']:
            raise ValueError('scanner_found_vulnerabilities')
        name = canonical(dep['name'])
        if name in scanned:
            raise ValueError('duplicate_scanner_dependency')
        scanned[name] = Version(dep['version'])
    if scanned != expected:
        raise ValueError('scanner_coverage_mismatch')
    return len(scanned)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--requirements', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    head = os.environ.get('PBT_HEAD_SHA', '')
    outcome = os.environ.get('AUDIT_OUTCOME', '')
    baseline_outcome = os.environ.get('AUDIT_BASELINE_OUTCOME', '')
    errors = []
    source = None
    text = ''
    action_output = ''
    count = None
    source_verified = False
    if not SHA.fullmatch(head):
        errors.append('invalid_head_sha')
    if outcome != 'success':
        errors.append('audit_step_not_successful')
    if baseline_outcome != 'success':
        errors.append('baseline_audit_not_successful')
    try:
        source = args.requirements.read_bytes()
        expected = required_packages(source)
    except (OSError, UnicodeError, ValueError) as exc:
        expected = None
        errors.append(f'requirements_invalid:{type(exc).__name__}:{str(exc) if isinstance(exc, ValueError) else "unavailable"}')
    if source is not None:
        try:
            verify_source_provenance(head, source, args.requirements)
            source_verified = True
        except ValueError as exc:
            errors.append(str(exc))
    try:
        text = args.report.read_bytes().decode('utf-8')
    except (OSError, UnicodeError) as exc:
        errors.append(f'scanner_output_unavailable:{type(exc).__name__}')
    try:
        action_output = base64.b64decode(os.environ.get('AUDIT_OUTPUT_B64', ''), validate=True).decode('utf-8')
    except (binascii.Error, UnicodeError):
        errors.append('invalid_action_output_encoding')
    if expected is not None and text:
        try:
            count = verify_report(text, expected)
        except ValueError as exc:
            errors.append(str(exc))
    elif not text and not any(e.startswith('scanner_output_unavailable:') for e in errors):
        errors.append('scanner_output_empty')
    try:
        version = metadata.version('pip-audit')
    except metadata.PackageNotFoundError:
        version = None
    if outcome == 'success':
        try:
            if version is None:
                raise ValueError('missing scanner version')
            Version(version)
        except ValueError:
            errors.append('scanner_version_unavailable_or_invalid')
    record = {
        'schema': 'pbt-osv-audit-receipt-v2',
        'head_sha': head,
        'action_commit': ACTION_COMMIT,
        'input': str(args.requirements),
        'requirements_sha256': hashlib.sha256(source).hexdigest() if source is not None else None,
        'requirements_match_head_blob': source_verified,
        'service': 'OSV', 'require_hashes': True, 'no_deps': True,
        'disable_pip': True, 'scanner_version': version,
        'outcome': outcome, 'baseline_outcome': baseline_outcome, 'validation_errors': errors,
        'dependency_count': count,
        'scanner_output_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
        'scanner_output': text,
        'action_failure_output': action_output,
        'claim_boundary': ('OSV checks known dependency vulnerabilities; require-hashes checks '
                           'presence, not distribution bytes; scanner version is not pinned; '
                           'this is not ASVS certification'),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, sort_keys=True, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
