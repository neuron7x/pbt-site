"""Fail-closed structural guard for the dependency-audit workflow.

This is a narrow workflow policy test, NOT a security scanner.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_dependency_audit_is_sha_pinned_and_cannot_ignore_failures():
    workflow = (ROOT / '.github/workflows/security-assurance.yml').read_text()
    assert 'pypa/gh-action-pip-audit@1220774d901786e6f652ae159f7b6bc8fea6d266' in workflow
    assert 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1' in workflow
    assert 'actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0' in workflow
    assert 'inputs: requirements.txt' in workflow
    assert 'no-deps: true' in workflow
    assert 'require-hashes: true' in workflow
    assert 'vulnerability-service: osv' in workflow
    assert 'if-no-files-found: error' in workflow
    assert 'continue-on-error:' not in workflow
    assert 'ignore-vulns:' not in workflow
    assert 'internal-be-careful-allow-failure:' not in workflow
    assert 'push:' not in workflow
    assert 'git rev-parse HEAD' in workflow
    assert 'head.sha' in workflow
