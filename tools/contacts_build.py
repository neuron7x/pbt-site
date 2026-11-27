#!/usr/bin/env python3
"""Реквізити у web/index.html — з одного джерела, config/business.json (наказ А4, крок 2).

До цього телефон, пошта, адреса, ЄДРПОУ, директор, банк і JSON-LD були вписані в розмітку руками й мусили збігатися
з config/business.json «на око». Тепер кожне таке місце — названий слот: інструмент вписує в нього значення з джерела.

Правила (fail-closed):
  • кожен слот має знайтись у розмітці щонайменше раз — зник слот, значить розмітку змінили повз інструмент;
  • телефон і пошта поза слотами — помилка: жорстко прописану копію не пропустить `--check`;
  • обов'язкове значення в джерелі порожнє — помилка; необов'язкове (директор, банк) порожнє — слот лишається порожнім:
    `null` означає «не вигадувати», рядок ховає web/js/site.js.

  python3 tools/contacts_build.py            — показати слоти й кількість місць
  python3 tools/contacts_build.py --write    — вписати значення у web/index.html
  python3 tools/contacts_build.py --check    — вихід 1, якщо розмітка не дорівнює виходу інструмента
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = Path('web/index.html')
PHONE_E164 = re.compile(r'\+380\d{9}')
PHONE_SHOWN = re.compile(r'\b0\d{2} \d{3} \d{2} \d{2}\b')
EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
PLACEHOLDER = re.compile(r'\splaceholder="[^"]*"')       # приклад формату в полі форми — не реквізит
JSON_LD = re.compile(r'(<script type="application/ld\+json">\n)(.*?)(\n</script>)', re.S)


class ContactsError(ValueError):
    pass


def shown_phone(e164):
    """+380675550317 → 067 555 03 17."""
    if not re.fullmatch(r'\+380\d{9}', e164 or ''):
        raise ContactsError(f'телефон {e164!r}: очікується +380 і 9 цифр')
    n = '0' + e164[4:]
    return f'{n[:3]} {n[3:6]} {n[6:8]} {n[8:]}'


def _text_slot(attribute):
    """Текст елемента з точним атрибутом data-…: <tag … data-x …>ТЕКСТ<"""
    return re.compile(r'(<[a-z0-9]+(?:\s[^<>]*)?\s' + re.escape(attribute) + r'(?=[\s>])[^<>]*>)([^<]*)(?=<)')


def facts(business):
    """Значення слотів із джерела; порожнє обов'язкове — помилка."""
    contacts, bank = business.get('contacts') or {}, business.get('bank') or {}
    required = {'contacts.phone': contacts.get('phone'), 'contacts.email': contacts.get('email'), 'address': business.get('address'),
                'edrpou': business.get('edrpou'), 'legalName': business.get('legalName'), 'city': business.get('city')}
    empty = sorted(k for k, v in required.items() if not v)
    if empty:
        raise ContactsError(f'config/business.json: порожні обов\'язкові поля {empty}')
    optional = {'director': business.get('director'), 'bank.name': bank.get('name'), 'bank.iban': bank.get('iban')}
    return {**required, **{k: v or '' for k, v in optional.items()}}       # null → порожній слот, нічого не вигадується


def slots(f):
    """(назва, шаблон із групою значення №2, значення)."""
    phone, email = f['contacts.phone'], f['contacts.email']
    return [
        ('tel-href', re.compile(r'(href="tel:)([^"]*)(?=")'), phone),
        ('phone-text', _text_slot('data-phone'), shown_phone(phone)),
        ('phone-channel', re.compile(r'(<span>Телефон</span><b>)([^<]*)(?=</b>)'), shown_phone(phone)),
        ('mailto-href', re.compile(r'(href="mailto:)([^"]*)(?=")'), email),
        ('email-text', _text_slot('data-email'), email),
        ('email-channel', re.compile(r'(<span>Електронна пошта</span><b>)([^<]*)(?=</b>)'), email),
        ('address-text', _text_slot('data-address'), f['address']),
        ('legal-text', _text_slot('data-legal'), f['legalName']),
        ('edrpou-text', _text_slot('data-edrpou'), 'ЄДРПОУ ' + f['edrpou']),
        ('director-text', _text_slot('data-director'), f['director']),
        ('bank-name-text', _text_slot('data-bank-name'), f['bank.name']),
        ('bank-iban-text', _text_slot('data-bank-iban'), f['bank.iban']),
    ]


def json_ld(current, business, f):
    """Похідні поля JSON-LD — із джерела; решта (перелік послуг) лишається як є. Порядок ключів і формат зберігаються."""
    data = json.loads(current)
    parts = [p.strip() for p in f['address'].split(',')]
    if len(parts) < 3 or not re.fullmatch(r'\d{5}', parts[0]):
        raise ContactsError(f'адреса {f["address"]!r}: очікується «індекс, місто, вулиця…»')
    phones = [f['contacts.phone']] + ([business['contacts']['phone2']] if business['contacts'].get('phone2') else [])
    data.update({'name': f['legalName'], 'alternateName': business['brand']['alternateName'], 'telephone': phones, 'email': f['contacts.email'],
                 'areaServed': [f'{region} область' for region in business['regions']]})
    data['identifier']['value'] = f['edrpou']
    data['address'].update({'streetAddress': ', '.join(parts[2:]), 'addressLocality': f['city'], 'postalCode': parts[0]})
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'))


def build(html, business):
    """Розмітка з уписаними значеннями та звіт {слот: кількість місць}."""
    f = facts(business)
    report = {}
    for name, pattern, value in slots(f):
        html, count = pattern.subn(lambda m, v=value: m.group(1) + v, html)
        if count == 0:
            raise ContactsError(f'слот «{name}» не знайдено в {HTML} — розмітку змінено повз інструмент')
        report[name] = count
    block = JSON_LD.search(html)
    if not block:
        raise ContactsError(f'блок JSON-LD не знайдено в {HTML}')
    html = html[:block.start(2)] + json_ld(block.group(2), business, f) + html[block.end(2):]
    report['json-ld'] = 1
    # після вписування кожне входження телефону й пошти мусить дорівнювати джерелу: чуже число = копія поза слотами
    phone, email = f['contacts.phone'], f['contacts.email']
    allowed_phones = {phone, business['contacts'].get('phone2')} - {None}
    scanned = PLACEHOLDER.sub('', html)
    stray = sorted({m for m in PHONE_E164.findall(scanned) if m not in allowed_phones}
                   | {m for m in PHONE_SHOWN.findall(scanned) if m not in {shown_phone(p) for p in allowed_phones}}
                   | {m for m in EMAIL.findall(scanned) if m != email})
    if stray:
        raise ContactsError(f'{HTML}: реквізити поза слотами {stray} — жорстко прописана копія')
    # і навіть правильне значення мусить стояти лише в слотах: зайве входження сьогодні збігається, а завтра відстане
    expected = {phone: report['tel-href'] + 1, shown_phone(phone): report['phone-text'] + report['phone-channel'],
                email: report['mailto-href'] + report['email-text'] + report['email-channel'] + 1}
    extra = {value: scanned.count(value) - count for value, count in expected.items() if scanned.count(value) != count}
    if extra:
        raise ContactsError(f'{HTML}: входження поза слотами (значення: різниця) {extra} — жорстко прописана копія')
    return html, report


def main(argv=None, root=ROOT):
    args = sys.argv[1:] if argv is None else argv
    sys.stdout.reconfigure(encoding='utf-8')
    path = root / HTML
    current = path.read_text(encoding='utf-8')
    try:
        business = json.loads((root / 'config/business.json').read_text(encoding='utf-8'))
        text, report = build(current, business)
    except (ContactsError, OSError, ValueError, KeyError) as exc:
        print(f'contacts_build: {exc}', file=sys.stderr)
        return 1
    if '--check' in args:
        if current != text:
            print('contacts_build: web/index.html не відповідає config/business.json — запустіть python3 tools/contacts_build.py --write', file=sys.stderr)
            return 1
        return 0
    if '--write' in args:
        path.write_text(text, encoding='utf-8')
    print(f'{HTML}: ' + ', '.join(f'{k}×{v}' for k, v in report.items()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
