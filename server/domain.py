"""Домен заявки: очищення, перевірка й нормалізація полів.

Часовий пояс залежить від tzdata. Перевірка дати бере поточний час, якщо момент не передано явно.

Винесено з server/app.py без зміни коду (наказ А1, крок 1). Словники й межі довжин — частина контракту з CRM
(AGENTS.md §1): вид rent|material|transport|other, спосіб зв'язку phone|telegram|viber|whatsapp,
тема 160, місце 160, ім'я 60, контакт 40, коментар 1000.
"""
import re
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TYPES = {'rent', 'material', 'transport', 'other'}
METHODS = {'phone', 'telegram', 'viber', 'whatsapp'}


# ─── валідація ───────────────────────────────────────────
CTRL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2066-\u2069]')  # Escapes: bidi controls must not sit literally in source.


def clean(v, maxlen, multiline=False):
    if v is None:
        return ''
    if not isinstance(v, (str, int, float)):
        raise ValueError('type')
    s = unicodedata.normalize('NFC', str(v))
    s.encode('utf-8')  # Reject lone JSON \uXXXX surrogates before hashing/storage.
    s = CTRL.sub('', s)
    if not multiline:
        s = re.sub(r'\s+', ' ', s)
    s = s.strip()
    if len(s) > maxlen:
        raise ValueError('length')
    return s


def validate(d):
    """Повертає (дані, помилки{поле: повідомлення})."""
    if not isinstance(d, dict):
        return None, {'_': 'Невірний формат запиту.'}
    err, out = {}, {}

    def put(field, fn):
        try:
            out[field] = fn()
        except ValueError:
            err[field] = MSG.get(field, 'Перевір поле.')

    def safe(v, n):   # S12: скінченні поля й пастка — невалідний тип/довжина = порожнє значення, а не виняток (фаззинг: обрив з'єднання)
        try:
            return clean(v, n)
        except ValueError:
            return None

    hp = safe(d.get('website'), 200)
    if hp is None or hp:                      # honeypot: будь-яке непорожнє чи невалідне значення = бот
        return None, {'_': 'spam'}
    t = safe(d.get('type'), 10) or ''
    if t not in TYPES:
        err['type'] = 'Обери тип запиту.'
    out['type'] = t
    put('subject', lambda: clean(d.get('subject'), 160))        # техніка / матеріал / маршрут
    put('hours', lambda: _int(d.get('hours'), 1, 5000))          # годин оренди (або м³/т для матеріалів)
    put('km', lambda: _int(d.get('km'), 0, 3000))                # км подачі / перевезення
    put('place', lambda: clean(d.get('place'), 160))              # об'єкт: місто, адреса
    put('date', lambda: _date(d.get('date')))                    # бажана дата початку
    put('name', lambda: clean(d.get('name'), 60))
    m = safe(d.get('method'), 12) or ''
    if m not in METHODS:
        err['method'] = 'Обери спосіб зв\'язку.'
    out['method'] = m
    put('contact', lambda: _contact(m, clean(d.get('contact'), 40)))
    put('comment', lambda: clean(d.get('comment'), 1000, multiline=True))

    # семантика за типом запиту
    if t in ('rent', 'material', 'transport') and len(out.get('subject', '')) < 2:
        err['subject'] = MSG_SUBJECT[t]
    if t == 'other' and len(out.get('comment', '')) < 5 and len(out.get('subject', '')) < 2:
        err['comment'] = 'Опиши задачу кількома словами.'
    return out, err


MSG = {'subject': 'До 160 символів.', 'hours': 'Ціле число від 1 до 5000.', 'km': 'Ціле число від 0 до 3000.',
       'place': 'Місто й адреса — до 160 символів.', 'date': 'Дата у форматі РРРР-ММ-ДД, не раніше сьогодні.',
       'name': 'Ім\'я — до 60 символів.', 'contact': 'Перевір контакт.', 'comment': 'Коментар — до 1000 символів.'}
MSG_SUBJECT = {'rent': 'Вкажи, яка техніка потрібна.', 'material': 'Вкажи матеріал і фракцію.', 'transport': 'Вкажи, що й куди перевезти.'}


def _int(v, lo, hi):
    if v in (None, ''):
        return None
    s = re.sub(r'[\s]', '', clean(v, 8))
    if not s.isdigit() or not lo <= int(s) <= hi:
        raise ValueError
    return int(s)


KYIV = ZoneInfo('Europe/Kyiv')


def kyiv_date(now=None):
    """The business operates on the Kyiv civil date, whatever TZ the host runs in."""
    return (now or datetime.now(timezone.utc)).astimezone(KYIV).date()


def date_allowed(value, now=None):
    if value == '':
        return True
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        return False
    try:
        return datetime.strptime(value, '%Y-%m-%d').date() >= kyiv_date(now)
    except ValueError:
        return False


def _date(v):
    if v in (None, ''):
        return ''
    s = clean(v, 10)
    if not s or not date_allowed(s):  # Whitespace is not an absent date.
        raise ValueError
    return s


def _contact(method, s):
    if not s:
        raise ValueError
    if method == 'telegram' and s.startswith('@'):
        if not re.fullmatch(r'@[A-Za-z0-9_]{5,32}', s):
            raise ValueError
        return s
    digits = re.sub(r'[\s()\-]', '', s)
    if re.fullmatch(r'0\d{9}', digits):
        digits = '+38' + digits
    if re.fullmatch(r'380\d{9}', digits):
        digits = '+' + digits
    if re.fullmatch(r'\+3800\d{9}', digits):   # FC-3: «+380 0XX…» (зайвий 0 за placeholder) → +380 + 9 цифр
        digits = '+380' + digits[5:]
    if digits.startswith('+380') and not re.fullmatch(r'\+380\d{9}', digits):   # FC-3: +380 — рівно 9 цифр; інші +38x не чіпаються
        raise ValueError
    if not re.fullmatch(r'\+\d{10,15}', digits):
        raise ValueError
    return digits
