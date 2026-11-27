#!/usr/bin/env python3
"""web/js/data.js — згенерований файл, а не третя копія правди (наказ А4, крок 1).

Джерела (кожне — єдине місце для своїх фактів):
  config/business.json  — реквізити фірми; службовий ключ `_status` назовні не йде;
  data/catalog.json     — категорії, парк, матеріали; поля `price` немає: ціну під заявку визначає керівник фірми; вписане — назовні не йде;
  content/site.json     — решта даних інтерфейсу: роботи, кадри, області, маршрути, тека відео.

Схема закрита: невідомий або відсутній ключ верхнього рівня в будь-якому джерелі — помилка, файл не записується.
Вихід детермінований: порядок ключів заданий тут, формат — json.dumps(indent=1), UTF-8 без екранування.

  python3 tools/data_build.py            — показати, що було б згенеровано (розмір, sha256)
  python3 tools/data_build.py --write    — записати web/js/data.js
  python3 tools/data_build.py --check    — вихід 1, якщо web/js/data.js не дорівнює виходу генератора
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path('web/js/data.js')
HEADER = ('/* Дані інтерфейсу ПЛЕЙНБУД — ЗГЕНЕРОВАНО tools/data_build.py, руками не правити. Джерела: config/business.json (реквізити), '
          'data/catalog.json (парк і матеріали, без цін), content/site.json (решта); факти каталогу від 03.10.2026 успадковано без '
          'нового затвердження; походження медіа — docs/PROVENANCE.md. */\n')
PRIVATE = ('_status',)                                     # службові нотатки для людей, не для сторінки
BUSINESS_KEYS = ('brand', 'legalName', 'edrpou', 'city', 'region', 'address', 'url', 'logo', 'contacts', 'responsiblePerson', 'hours',
                 'regions', 'director', 'bank')
CATALOG_KEYS = ('cats', 'fleet', 'materials')
ITEM_PRIVATE = ('price',)                                  # другий бар'єр: ціни в каталозі немає, а вписана — на сторінку не йде (acb1b22)
PRICED = ('fleet', 'materials')
SITE_KEYS = ('jobs', 'proof', 'regions', 'routes', 'video')
ORDER = ('business', 'cats', 'fleet', 'materials', 'jobs', 'proof', 'regions', 'routes', 'video')


class SourceError(ValueError):
    pass


def _load(root, rel, allowed, private=()):
    path = root / rel
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise SourceError(f'{rel}: не читається — {exc}') from exc
    if not isinstance(data, dict):
        raise SourceError(f'{rel}: очікується об\'єкт')
    keys = [k for k in data if k not in private]
    unknown, missing = sorted(set(keys) - set(allowed)), sorted(set(allowed) - set(keys))
    if unknown or missing:
        raise SourceError(f'{rel}: невідомі ключі {unknown}, бракує {missing}')
    return {k: data[k] for k in keys}


def build(root=ROOT):
    """Текст web/js/data.js із трьох джерел."""
    business = _load(root, 'config/business.json', BUSINESS_KEYS, PRIVATE)
    catalog = _load(root, 'data/catalog.json', CATALOG_KEYS)
    for key in PRICED:
        catalog[key] = [{k: v for k, v in item.items() if k not in ITEM_PRIVATE} for item in catalog[key]]
    site = _load(root, 'content/site.json', SITE_KEYS)
    merged = {'business': business, **catalog, **site}
    assert set(merged) == set(ORDER) and len(merged) == len(ORDER)
    page = {k: merged[k] for k in ORDER}
    return HEADER + 'window.PBT = ' + json.dumps(page, ensure_ascii=False, indent=1) + ';\n'


def main(argv=None, root=ROOT):
    args = sys.argv[1:] if argv is None else argv
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        text = build(root)
    except SourceError as exc:
        print(f'data_build: {exc}', file=sys.stderr)
        return 1
    out = root / OUT
    if '--check' in args:
        current = out.read_text(encoding='utf-8') if out.is_file() else ''
        if current != text:
            print('data_build: web/js/data.js не відповідає джерелам — запустіть python3 tools/data_build.py --write', file=sys.stderr)
            return 1
        return 0
    if '--write' in args:
        out.write_text(text, encoding='utf-8')
    print(f'{OUT}: {len(text.encode("utf-8"))} байтів, sha256 {hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
