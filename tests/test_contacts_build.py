"""Наказ А4, крок 2: реквізити у web/index.html — з config/business.json, а не рукописна копія.

Критерій наказу: зміна телефону в одному файлі міняє всі місця. Тут — саме це для розмітки: JSON-LD, tel:, видимий текст.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import tools.contacts_build as contacts_build        # прямий імпорт нового модуля: на базі без нього тести «заблоковані новим модулем»

ROOT = Path(__file__).resolve().parent.parent
FILES = ('config/business.json', 'web/index.html', 'tools/contacts_build.py')


def _tree(tmp_path):
    tree = tmp_path / 'tree'
    for rel in FILES:
        (tree / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, tree / rel)
    return tree


def _run(tree, *args):
    return subprocess.run([sys.executable, '-s', 'tools/contacts_build.py', *args], cwd=tree, capture_output=True, text=True)


def _business(tree, change):
    path = tree / 'config/business.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    change(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _html(tree, change=None):
    path = tree / 'web/index.html'
    text = path.read_text(encoding='utf-8')
    if change:
        text = change(text)
        path.write_text(text, encoding='utf-8')
    return text


def _json_ld(text):
    return json.loads(re.search(r'<script type="application/ld\+json">\n(.*?)\n</script>', text, re.S).group(1))


def test_markup_equals_tool_output():
    business = json.loads((ROOT / 'config/business.json').read_text(encoding='utf-8'))
    current = (ROOT / 'web/index.html').read_text(encoding='utf-8')
    text, report = contacts_build.build(current, business)
    assert text == current, 'web/index.html відстав від config/business.json: python3 tools/contacts_build.py --write'
    assert report['tel-href'] >= 10 and report['phone-text'] >= 4 and report['json-ld'] == 1, report


def test_changing_the_phone_in_one_file_changes_every_occurrence(tmp_path):
    tree = _tree(tmp_path)
    before = _html(tree)
    old = json.loads((tree / 'config/business.json').read_text(encoding='utf-8'))['contacts']['phone']
    old_shown, new, new_shown = contacts_build.shown_phone(old), '+380501234567', '050 123 45 67'
    counts = (before.count(old), before.count(old_shown))
    assert counts[0] >= 11 and counts[1] >= 5, counts                    # tel: ×10 + JSON-LD; видимий текст ×5
    _business(tree, lambda d: d['contacts'].update(phone=new))
    assert _run(tree, '--check').returncode == 1                        # джерело змінилось — розмітка відстала
    written = _run(tree, '--write')
    assert written.returncode == 0, written.stderr
    after = _html(tree)
    assert (after.count(old), after.count(old_shown)) == (0, 0)         # жодного старого входження
    assert (after.count(new), after.count(new_shown)) == counts         # кожне місце змінилось, жодне не зникло
    assert _json_ld(after)['telephone'] == [new]
    assert f'href="tel:{old}"' not in after and after.count(f'href="tel:{new}"') == counts[0] - 1
    assert _run(tree, '--check').returncode == 0


def test_changing_the_email_and_identity_reaches_markup_and_json_ld(tmp_path):
    tree = _tree(tmp_path)
    _business(tree, lambda d: (d['contacts'].update(email='office@example.org'), d.update(edrpou='00000001', address='01001, м. Київ, вул. Перша, буд. 1', city='Київ')))
    assert _run(tree, '--write').returncode == 0
    after = _html(tree)
    ld = _json_ld(after)
    assert 'plainbud@gmail.com' not in after and after.count('office@example.org') >= 7
    assert ld['email'] == 'office@example.org' and ld['identifier']['value'] == '00000001'
    assert ld['address'] == {'@type': 'PostalAddress', 'streetAddress': 'вул. Перша, буд. 1', 'addressLocality': 'Київ', 'postalCode': '01001', 'addressCountry': 'UA'}
    assert after.count('01001, м. Київ, вул. Перша, буд. 1') == 3 and 'ЄДРПОУ 00000001' in after


def test_json_ld_keeps_the_offer_list_and_takes_identity_from_the_source():
    business = json.loads((ROOT / 'config/business.json').read_text(encoding='utf-8'))
    ld = _json_ld((ROOT / 'web/index.html').read_text(encoding='utf-8'))
    assert ld['@type'] == 'LocalBusiness' and ld['makesOffer']
    assert ld['name'] == business['legalName'] and ld['telephone'][0] == business['contacts']['phone']
    assert ld['areaServed'] == [f'{r} область' for r in business['regions']]


@pytest.mark.parametrize('copy', [
    '<p>050 111 22 33</p>',                       # чужий номер
    '<p>067 555 03 17</p>',                       # чинний номер, але поза слотом: завтра відстане
    '<a href="https://example.org/?p=+380675550317">x</a>',
    '<p>someone@example.org</p>',
])
def test_a_hardcoded_copy_outside_the_slots_fails_closed(tmp_path, copy):
    tree = _tree(tmp_path)
    _html(tree, lambda text: text.replace('</footer>', copy + '</footer>', 1))
    before = _html(tree)
    for mode in ('--check', '--write'):
        result = _run(tree, mode)
        assert result.returncode == 1 and 'поза слотами' in result.stderr, (mode, result.stderr)
    assert _html(tree) == before                                         # нічого не записано


def test_a_form_placeholder_is_an_example_not_a_contact():
    assert 'placeholder="067 000 00 00"' in (ROOT / 'web/index.html').read_text(encoding='utf-8')
    assert _run(ROOT, '--check').returncode == 0


def test_a_missing_slot_fails_closed(tmp_path):
    tree = _tree(tmp_path)
    _html(tree, lambda text: text.replace(' data-edrpou>', '>', 1))
    result = _run(tree, '--write')
    assert result.returncode == 1 and 'edrpou-text' in result.stderr


def test_an_empty_required_fact_fails_and_an_empty_optional_one_is_not_invented(tmp_path):
    tree = _tree(tmp_path)
    _business(tree, lambda d: d['contacts'].update(email=None))
    result = _run(tree, '--write')
    assert result.returncode == 1 and 'contacts.email' in result.stderr
    tree = _tree(tmp_path / 'optional')
    _business(tree, lambda d: d.update(director=None, bank=None))
    assert _run(tree, '--write').returncode == 0
    after = _html(tree)
    assert '<span data-director></span>' in after and 'data-bank-iban></span>' in after and 'UA39' not in after


def test_malformed_phone_or_address_is_rejected(tmp_path):
    for change, word in ((lambda d: d['contacts'].update(phone='067 555 03 17'), 'телефон'), (lambda d: d.update(address='Полтава'), 'адреса')):
        tree = _tree(tmp_path / word)
        _business(tree, change)
        result = _run(tree, '--write')
        assert result.returncode == 1 and word in result.stderr, result.stderr
