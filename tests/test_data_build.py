"""Наказ А4, крок 1: web/js/data.js — згенерований із джерел, а не третя копія правди.

Критерій наказу для цього кроку: факт міняють в одному джерелі, і він міняється на сторінці; розбіжність ловить гейт,
а не око. Тут — саме це, плюс закрита схема джерел і детермінізм.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import tools.data_build as data_build        # прямий імпорт нового модуля: на базі без нього тести «заблоковані новим модулем»

ROOT = Path(__file__).resolve().parent.parent

SOURCES = ('config/business.json', 'data/catalog.json', 'content/site.json')


def _tree(tmp_path):
    tree = tmp_path / 'tree'
    for rel in SOURCES + ('web/js/data.js', 'tools/data_build.py'):
        (tree / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, tree / rel)
    return tree


def _run(tree, *args):
    return subprocess.run([sys.executable, '-s', 'tools/data_build.py', *args], cwd=tree, capture_output=True, text=True)


def _page(path):
    """Те, що побачить браузер: виконати data.js у порожньому вікні."""
    code = ("const fs=require('fs'),vm=require('vm');const w={};vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),{window:w});"
            "process.stdout.write(JSON.stringify(w.PBT))")
    return json.loads(subprocess.run(['node', '-e', code, str(path)], capture_output=True, text=True, timeout=30, check=True).stdout)


def test_committed_file_is_exactly_what_the_generator_emits():
    assert (ROOT / 'web/js/data.js').read_text(encoding='utf-8') == data_build.build(ROOT)
    assert subprocess.run([sys.executable, '-s', 'tools/data_build.py', '--check'], cwd=ROOT, capture_output=True).returncode == 0


def test_page_data_equals_the_three_sources_and_nothing_else():
    page = _page(ROOT / 'web/js/data.js')
    business = json.loads((ROOT / 'config/business.json').read_text(encoding='utf-8'))
    catalog = json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))
    site = json.loads((ROOT / 'content/site.json').read_text(encoding='utf-8'))
    assert list(page) == list(data_build.ORDER)
    assert page['business'] == {k: v for k, v in business.items() if k != '_status'}
    public = {k: ([{f: v for f, v in item.items() if f != 'price'} for item in v] if k in ('fleet', 'materials') else v) for k, v in catalog.items()}
    assert {k: page[k] for k in catalog} == public                       # каталог без внутрішньої ціни позиції
    assert {k: page[k] for k in site} == site
    assert set(page) == {'business'} | set(catalog) | set(site)          # жодного факту без джерела
    assert not set(catalog) & set(site)                                   # і жодного факту з двох джерел


def test_private_status_note_never_reaches_the_page():
    business = json.loads((ROOT / 'config/business.json').read_text(encoding='utf-8'))
    assert business['_status'], 'у джерелі є службова нотатка — інакше тест нічого не перевіряє'
    text = data_build.build(ROOT)
    assert '_status' not in text and business['_status'][:40] not in text
    assert '_status' not in _page(ROOT / 'web/js/data.js')['business']


def test_internal_catalog_price_never_reaches_the_page():
    catalog = json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))
    priced = [i for i in catalog['fleet'] + catalog['materials'] if i.get('price') is not None]
    assert len(priced) >= 20, 'у каталозі є внутрішні ціни — інакше тест нічого не перевіряє'
    page = _page(ROOT / 'web/js/data.js')
    assert all('price' not in item for item in page['fleet'] + page['materials'])
    assert '"price"' not in data_build.build(ROOT)


def test_check_fails_when_a_source_changes_until_the_file_is_rebuilt(tmp_path):
    tree = _tree(tmp_path)
    assert _run(tree, '--check').returncode == 0
    source = tree / 'config/business.json'
    business = json.loads(source.read_text(encoding='utf-8'))
    old, new = business['contacts']['phone'], '+380501112233'
    assert old != new and old in (tree / 'web/js/data.js').read_text(encoding='utf-8')
    business['contacts']['phone'] = new
    source.write_text(json.dumps(business, ensure_ascii=False, indent=2), encoding='utf-8')
    drift = _run(tree, '--check')
    assert drift.returncode == 1 and 'не відповідає джерелам' in drift.stderr
    assert old in (tree / 'web/js/data.js').read_text(encoding='utf-8')   # --check нічого не переписує
    assert _run(tree, '--write').returncode == 0
    rebuilt = (tree / 'web/js/data.js').read_text(encoding='utf-8')
    assert new in rebuilt and old not in rebuilt                          # факт змінено в одному місці — сторінка пішла слідом
    assert _page(tree / 'web/js/data.js')['business']['contacts']['phone'] == new
    assert _run(tree, '--check').returncode == 0


@pytest.mark.parametrize('rel,mutate', [
    ('content/site.json', lambda d: d.update(routez=d.pop('routes'))),          # одруківка в назві поля
    ('content/site.json', lambda d: d.update(extra=1)),                         # зайве поле
    ('data/catalog.json', lambda d: d.pop('fleet')),                            # зникле поле
    ('config/business.json', lambda d: d.update(phone='+380000000000')),        # факт не на своєму місці
], ids=['typo', 'extra', 'missing', 'misplaced'])
def test_unknown_or_missing_source_key_is_an_error_and_nothing_is_written(tmp_path, rel, mutate):
    tree = _tree(tmp_path)
    before = (tree / 'web/js/data.js').read_bytes()
    data = json.loads((tree / rel).read_text(encoding='utf-8'))
    mutate(data)
    (tree / rel).write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    for mode in ('--write', '--check'):
        run = _run(tree, mode)
        assert run.returncode == 1 and rel in run.stderr, (mode, run.stderr)
    assert (tree / 'web/js/data.js').read_bytes() == before


def test_unreadable_source_is_reported_not_swallowed(tmp_path):
    tree = _tree(tmp_path)
    (tree / 'content/site.json').write_text('{ не json', encoding='utf-8')
    run = _run(tree, '--write')
    assert run.returncode == 1 and 'content/site.json' in run.stderr and 'Traceback' not in run.stderr


def test_generation_is_deterministic_across_hash_seeds_and_locales():
    runs = [subprocess.run([sys.executable, '-s', '-c', 'import sys; sys.path.insert(0, "tools"); import data_build; sys.stdout.buffer.write(data_build.build().encode())'],
                           cwd=ROOT, capture_output=True, env={'PYTHONHASHSEED': seed, 'PATH': '/usr/bin:/bin', 'LC_ALL': locale})
            for seed, locale in (('0', 'C'), ('1', 'C.UTF-8'), ('4242', 'POSIX'))]
    assert [r.returncode for r in runs] == [0, 0, 0], [r.stderr[-200:] for r in runs]
    assert len({r.stdout for r in runs}) == 1 and runs[0].stdout.decode('utf-8') == data_build.build(ROOT)
