#!/usr/bin/env python3
"""Validate owner-signed receipts for facts no test can establish. A file existing is not evidence.

Each receipt: assurance/evidence/external/<CLASS>.json with a detached <CLASS>.json.sig made by
`ssh-keygen -Y sign -n pbt-external-receipt`, verified against config/owner-allowed-signers. Fields, subject and
expiry come from config/external-evidence-policy.json. Signature proves who stated it, not that it is true.
"""
import argparse
from datetime import date
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


class ReceiptRejected(ValueError):
    pass


def _verify_signature(path, signers, policy):
    if not signers.is_file() or not signers.read_text(encoding='utf-8').strip():
        raise ReceiptRejected('no_authorized_signer')
    signature = Path(f'{path}.sig')
    if not signature.is_file():
        raise ReceiptRejected('unsigned')
    with path.open('rb') as message:
        run = subprocess.run(['ssh-keygen', '-Y', 'verify', '-f', str(signers), '-I', policy['signer_identity'],
                              '-n', policy['namespace'], '-s', str(signature)], stdin=message, capture_output=True, timeout=20)
    if run.returncode != 0:
        raise ReceiptRejected('bad_signature')


def validate(path, class_id, policy, signers, target_sha, today=None):
    rule = policy['classes'].get(class_id)
    if rule is None:
        raise ReceiptRejected('unknown_class')
    if not path.is_file():
        raise ReceiptRejected('absent')
    _verify_signature(path, signers, policy)
    try:
        receipt = json.loads(path.read_text(encoding='utf-8'))
    except ValueError:
        raise ReceiptRejected('unparsable') from None
    if receipt.get('schema') != 'pbt-external-receipt-v1' or receipt.get('class') != class_id:
        raise ReceiptRejected('wrong_class')
    for field in rule['fields']:
        if receipt.get(field) in (None, '', []):
            raise ReceiptRejected(f'missing_{field}')
    if receipt.get('revoked'):
        raise ReceiptRejected('revoked')
    if rule.get('expires'):
        try:
            expires = date.fromisoformat(receipt.get('expires_on', ''))
        except (ValueError, TypeError):
            raise ReceiptRejected('expiry_required') from None
        if expires < (today or date.today()):
            raise ReceiptRejected('expired')
    if rule.get('bound_to_target') and receipt.get('release_sha') != target_sha:
        raise ReceiptRejected('other_revision')
    return receipt


def status_all(root, target_sha, today=None):
    policy = json.loads((root / 'config/external-evidence-policy.json').read_text(encoding='utf-8'))
    signers = root / 'config/owner-allowed-signers'
    result = {}
    for class_id in policy['classes']:
        try:
            validate(root / 'assurance/evidence/external' / f'{class_id}.json', class_id, policy, signers, target_sha, today)
            result[class_id] = 'PASS'
        except (ReceiptRejected, OSError, subprocess.SubprocessError) as exc:
            result[class_id] = f'UNKNOWN:{exc}'
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--target-sha', required=True)
    a = p.parse_args(argv)
    result = status_all(ROOT, a.target_sha)
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0 if all(v == 'PASS' for v in result.values()) else 3


if __name__ == '__main__':
    sys.exit(main())
