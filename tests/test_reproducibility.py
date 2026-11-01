"""EVD-07: the offline bundle is a function of the source tree, not of locale, timezone or clock.

Scope: dist/ only, on this interpreter and these inputs. No reproducible-build claim for the whole system:
browsers, media encoders and CI images are not pinned to byte identity. See docs/ASSURANCE.md.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
ENVIRONMENTS = [{'TZ': 'UTC', 'LC_ALL': 'C'}, {'TZ': 'Pacific/Auckland', 'LC_ALL': 'C.UTF-8', 'PYTHONHASHSEED': '1'},
                {'TZ': 'America/Los_Angeles', 'LC_ALL': 'POSIX', 'PYTHONHASHSEED': '4242'}]


def _build(tree, env):
    shutil.rmtree(tree / 'dist', ignore_errors=True)
    subprocess.run([sys.executable, 'tools/inline.py'], cwd=tree, env={**os.environ, **env}, check=True,
                   capture_output=True, timeout=180)
    return {p.relative_to(tree / 'dist').as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((tree / 'dist').rglob('*')) if p.is_file()}


def _tree(tmp):
    tree = tmp / 'tree'
    for name in ('tools', 'config', 'web', 'data'):
        shutil.copytree(ROOT / name, tree / name, ignore=shutil.ignore_patterns('*.db*', '*.log', '.ip_salt', '__pycache__'))
    return tree


def test_bundle_bytes_do_not_depend_on_locale_timezone_or_hash_seed(tmp_path):
    tree = _tree(tmp_path)
    results = [_build(tree, env) for env in ENVIRONMENTS]
    assert results[0], 'build produced nothing: the comparison would be vacuous'
    assert results[0] == results[1] == results[2]


def test_comparison_detects_a_nondeterministic_input(tmp_path):
    tree = _tree(tmp_path)
    clean = _build(tree, ENVIRONMENTS[0])
    site = tree / 'web/js/site.js'
    site.write_text(site.read_text(encoding='utf-8') + '\n/* changed input */\n', encoding='utf-8')
    assert _build(tree, ENVIRONMENTS[0]) != clean
