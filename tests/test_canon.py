"""Статут (docs/CANON.md) і бібліографія не мають права посилатися в порожнечу: кожен названий файл, тест і ціль існують."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANON = (ROOT / 'docs' / 'CANON.md').read_text(encoding='utf-8')
BIBLIO = (ROOT / 'docs' / 'BIBLIOGRAPHY.md').read_text(encoding='utf-8')
PATH = re.compile(r'`((?:tools|tests|server|docs|config|web|ops|assurance|\.github)/[^`*\s]*|AGENTS\.md|Makefile)`')


def _paths(text):
    return sorted(set(PATH.findall(text)))


def test_every_path_named_in_the_canon_and_bibliography_exists():
    for name, text in (('CANON', CANON), ('BIBLIOGRAPHY', BIBLIO)):
        paths = _paths(text)
        assert len(paths) >= 15, (name, len(paths))
        missing = [p for p in paths if not (ROOT / p).exists()]
        assert not missing, (name, missing)


def test_every_make_target_named_in_the_canon_exists():
    makefile = (ROOT / 'Makefile').read_text(encoding='utf-8')
    targets = set(re.findall(r'^([a-z][a-z-]*):', makefile, re.M))
    named = set(re.findall(r'`make ([a-z-]+)`', CANON)) | set(re.findall(r'`(js|sky|crane|data|contacts|test|bundle|media-audit)`', CANON))
    assert {'gate', 'sky', 'crane'} <= named
    assert named <= targets, named - targets
    gate = re.search(r'^gate:([^#\n]*)', makefile, re.M).group(1).split()
    stated = re.search(r'`make gate`: (.+?), після чого', CANON).group(1)
    assert [t.strip('` ') for t in stated.split('→')] == gate          # порядок гейту в статуті = порядок у Makefile


def test_every_invariant_row_names_a_check_that_exists_and_is_collected():
    rows = re.findall(r'^\| ([DUG]-\d+) \| (.+?) \| (.+?) \|$', CANON, re.M)
    assert len(rows) == 22, len(rows)
    assert len({r[0] for r in rows}) == len(rows)
    for ident, _, checks in rows:
        files = re.findall(r'`(tests/test_[a-z0-9_]+\.py)`', checks)
        assert files, ident
        for f in files:
            assert re.search(r'^def test_', (ROOT / f).read_text(encoding='utf-8'), re.M), (ident, f)


def test_counts_stated_in_the_canon_match_the_assurance_files():
    import json
    obligations = len(json.loads((ROOT / 'assurance' / 'ledger.json').read_text(encoding='utf-8'))['obligations'])
    claims = len(json.loads((ROOT / 'assurance' / 'case.json').read_text(encoding='utf-8'))['claims'])
    assert f'{obligations} зобов\'язань, {claims} тверджень' in CANON
    workflows = sorted(p.name for p in (ROOT / '.github' / 'workflows').glob('*.yml'))
    assert len(workflows) == 7 and all(f'`{w}`' in CANON for w in workflows), workflows


def test_bibliography_status_counts_are_the_ones_it_states():
    marks = re.findall(r'\| (✔|◐|▲) \|$', BIBLIO, re.M)
    stated = re.search(r'(\d+) записів звірено пошуком \(`✔`\), (\d+) підтверджено вторинно \(`▲`\), (\d+) \(`◐`\)', BIBLIO)
    assert stated, 'рядок підсумку статусів зник'
    assert (marks.count('✔'), marks.count('▲'), marks.count('◐')) == tuple(map(int, stated.groups()))


def test_canon_claims_no_certification():
    assert 'не заявляється' in CANON and 'PRODUCTION HOLD' in CANON
    for forbidden in ('сертифіковано', 'відповідає WCAG', 'відповідає ASVS', 'SLSA level'):
        assert forbidden not in CANON, forbidden
