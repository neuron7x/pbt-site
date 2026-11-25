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
    # -s: без користувацького site-packages. Його .pth-файли — не вхід збірки; під LC_ALL=C Python 3.12 читає їх як ASCII
    # і падає ще до tools/inline.py, якщо шлях у .pth не латиницею (стенд розробника; у CI каталогу немає).
    proc = subprocess.run([sys.executable, '-s', 'tools/inline.py'], cwd=tree, env={**os.environ, **env},
                          check=False, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        # A size-guarded package can fail *deterministically* while remaining
        # genuinely unreleasable. No other builder error counts as success.
        assert 'Multifile artifact exceeds' in proc.stderr, proc.stderr
        budget = tree / 'dist' / 'artifact-budget.json'
        assert budget.is_file(), 'A failed publish must leave byte/digest evidence'
        import json
        report = json.loads(budget.read_text(encoding='utf-8'))
        assert report['ok'] is False and report['over_budget_bytes'] > 0
    result = {p.relative_to(tree / 'dist').as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted((tree / 'dist').rglob('*')) if p.is_file()}
    result['__builder_exit__'] = str(proc.returncode)
    return result


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
