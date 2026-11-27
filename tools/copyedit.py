#!/usr/bin/env python3
"""Коректура джерел даних сайту (content/site.json і data/catalog.json; web/js/data.js генерується з них) — детерміновано й ідемпотентно (повторний запуск нічого не змінює).
Норма: правопис 2019, ДСТУ 3582 (скорочення одиниць), типографіка: апостроф ’ (U+2019), нерозривний пробіл між числом
і одиницею, тире – в діапазонах, марки — у написанні виробника. Дані не вигадуємо: лише форма, не значення.
Запуск: python3 tools/copyedit.py [--check] — з --check код 1, якщо щось ще не нормалізовано (для тесту)."""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NBSP = ' '

NAMES = {   # назви техніки й матеріалів: правопис + написання марок
    'Гусеничний екскаватор VOLVO EC240': 'Гусеничний екскаватор Volvo EC240',
    'Гусеничний екскаватор DOOSAN DX300': 'Гусеничний екскаватор Doosan DX300',
    'Гусеничний екскаватор VOLVO EC480': 'Гусеничний екскаватор Volvo EC480',
    'Бульдозер KOMATSU D85ex': 'Бульдозер Komatsu D85EX',
    'Бульдозер викорчовувач KOMATSU D61': 'Бульдозер-викорчовувач Komatsu D61',
    'Автокран 25 т КРАЗ/МАЗ/КАМАЗ': 'Автокран 25 т КрАЗ / МАЗ / КамАЗ',
    'Автокран 55 т CHANG JIANG LT1055/1': 'Автокран 55 т Chang Jiang LT1055/1',
    'Автокран 120 т LIEBHERR LTM 1120': 'Автокран 120 т Liebherr LTM 1120',
    'Плаваючий екскаватор-амфібія VOLVO EC210BLR': 'Плавучий екскаватор-амфібія Volvo EC210BLR',
    'Плаваючий екскаватор-амфібія Hyundai 140-7A Big Float': 'Плавучий екскаватор-амфібія Hyundai 140-7A Big Float',
    'Екскаватор з довгою стрілою VOLVO EC210': 'Екскаватор із довгою стрілою Volvo EC210',
    'Екскаватор з довгою стрілою HITACHI ZX 210 LC': 'Екскаватор із довгою стрілою Hitachi ZX210LC',
    'Напівпричипи': 'Напівпричепи',
    'Фронтальний навантажувач CATERPILLAR 972K': 'Фронтальний навантажувач Caterpillar 972K',
    'Фронтальний навантажувач DOOSAN DL 400': 'Фронтальний навантажувач Doosan DL400',
    'Міні екскаватор-навантажувач': 'Мініекскаватор-навантажувач',
    'Мобільна щокова дробарка EXTEC C12+': 'Мобільна щокова дробарка Extec C12+',
    'Мульчер на базі мінінавантажувача GEHL': 'Мульчер на базі мінінавантажувача Gehl',
    'Мульчер RAPTOR 300': 'Мульчер Raptor 300',
    'Фракція 5×20': 'Фракція 5–20 мм', 'Фракція 20×40': 'Фракція 20–40 мм', 'Фракція 40×70': 'Фракція 40–70 мм',
    'ЩПС 0-40, 0-70': 'ЩПС 0–40, 0–70',
}
SPEC_KEYS = {'Вага': 'Маса', 'Витрати палива': 'Витрата палива', 'Ківш': 'Обладнання'}
VALUES = {'фронатальний, вила': 'фронтальний ківш, вила'}
DOCS = {
    'протокол Кременчуцький річпорт 2024': 'протокол випробувань, Кременчуцький річковий порт, 2024',
    'паспорт якості 5-20': 'паспорт якості, фракція 5–20', 'паспорт якості 20-40': 'паспорт якості, фракція 20–40',
    'паспорт якості 40-70': 'паспорт якості, фракція 40–70', 'паспорт якості 0-5': 'паспорт якості, фракція 0–5',
}
CATS = {'amph': ('Амфібії й довгі стріли', None),
        'crane': (None, '25–120 т, стріла до 70 м: монтаж, демонтаж, розбирання завалів.'),
        'road': (None, 'Грейдер, котки, асфальтоукладач, мінітехніка.')}
JOBS = {
    'lis': {'t': 'Розчищення ділянок, корчування', 'b': ['Рубка дерев', 'Корчування пнів', 'Мульчування порослі']},
    'demont': {'b': ['Знесення будівель', 'Гідромолот, гідроножиці', 'Розбирання завалів автокраном'],
               'subject': 'Демонтаж: екскаватор із гідромолотом'},
}


def typo(s):
    s = re.sub(r"(?<=[А-ЯІЇЄҐа-яіїєґ])'(?=[А-ЯІЇЄҐа-яіїєґ])", '’', s)                     # апостроф
    s = re.sub(r'(\d)\s?(т|л|м|км|мм|год)(?=$|[\s,.;:)/])', lambda m: m.group(1) + NBSP + m.group(2), s)   # 22т → 22 т
    return s


def fix(d):
    for c in d.get('cats', []):
        n, lead = CATS.get(c['id'], (None, None))
        if n: c['name'] = n
        if lead: c['lead'] = lead
        c['name'], c['lead'] = typo(c['name']), typo(c['lead'])
    for u in d.get('fleet', []):
        u['name'] = typo(NAMES.get(u['name'], u['name']))
        for sp in u.get('specs', []):
            sp['k'] = SPEC_KEYS.get(sp['k'], sp['k'])
            sp['v'] = typo(VALUES.get(sp['v'], sp['v']))
    for m in d.get('materials', []):
        m['name'] = typo(NAMES.get(m['name'], m['name']))
        if m.get('doc'): m['doc'] = typo(DOCS.get(m['doc'], m['doc']))
        if m.get('group'): m['group'] = typo(m['group'])
    for j in d.get('jobs', []):
        for k, v in JOBS.get(j['id'], {}).items():
            j[k] = v
        j['t'], j['v'] = typo(j['t']), typo(j['v'])
        j['b'] = [typo(x) for x in j['b']]; j['subject'] = typo(j['subject'])
    for p in d.get('proof', []):
        p['t'], p['s'] = typo(p['t']), typo(p['s'])
    return d


def main():
    check = '--check' in sys.argv
    dirty = []
    # джерела даних; web/js/data.js генерується з них (tools/data_build.py) і тут не правиться
    site = ROOT / 'content' / 'site.json'
    d = json.loads(site.read_text(encoding='utf-8')); before = json.dumps(d, ensure_ascii=False)
    fix(d)
    if json.dumps(d, ensure_ascii=False) != before:
        dirty.append('content/site.json')
        if not check:
            site.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    cat = ROOT / 'data' / 'catalog.json'
    c = json.loads(cat.read_text(encoding='utf-8')); before = json.dumps(c, ensure_ascii=False)
    fix(c)
    if json.dumps(c, ensure_ascii=False) != before:
        dirty.append('data/catalog.json')
        if not check:
            cat.write_text(json.dumps(c, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    if dirty and not check:                              # джерела змінились — згенерований файл мусить піти слідом
        import subprocess
        subprocess.run([sys.executable, str(ROOT / 'tools' / 'data_build.py'), '--write'], check=True, stdout=subprocess.DEVNULL)
    print(('не нормалізовано: ' if check else 'змінено: ') + (', '.join(dirty) or '—'))
    sys.exit(1 if check and dirty else 0)


if __name__ == '__main__':
    main()
