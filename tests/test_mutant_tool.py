"""tools/mutant_new.py — каталог мутантів канонічний і кожен запис застосовний (find рівно раз у своєму файлі)."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import mutant_new  # noqa: E402


def test_catalog_is_canonical_and_every_edit_applies():
    r = subprocess.run([sys.executable, 'tools/mutant_new.py', 'check'], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


@pytest.mark.parametrize('bad, why', [
    ({'id': 'M-A', 'edits': [{'file': 'web/js/site.js', 'find': 'ЦЬОГО РЯДКА НЕМА', 'replace': 'x'}], 'oracle': ['t']}, '0 раз'),
    ({'id': 'M-A', 'edits': [{'file': 'web/js/site.js', 'find': 'const', 'replace': 'x'}], 'oracle': ['t']}, 'має 1'),
    ({'id': 'M-A', 'edits': [], 'oracle': []}, 'без оракула'),
    ({'id': 'M-A', 'expected': 'UNTESTABLE', 'reason': 'бо'}, 'UNTESTABLE'),
])
def test_problems_are_caught(bad, why):
    assert any(why in p for p in mutant_new.problems({'mutants': [bad]})), why


def test_duplicate_ids_and_non_canonical_order_are_caught():
    d = {'schema': 's', 'mutants': [{'id': 'M-B', 'expected': 'UNTESTABLE', 'reason': 'x' * 40},
                                     {'id': 'M-A', 'expected': 'UNTESTABLE', 'reason': 'x' * 40}]}
    assert json.dumps(d, ensure_ascii=False, indent=1) + '\n' != mutant_new.canonical(d)
    assert [m['id'] for m in json.loads(mutant_new.canonical(d))['mutants']] == ['M-A', 'M-B']
    assert any('повторюється' in p for p in mutant_new.problems({'mutants': d['mutants'] * 2}))
