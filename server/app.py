#!/usr/bin/env python3
"""ПБТ · ПолтаваБудТехніка — статичний фронтенд + API заявок (успадковано з lube-avto server/app.py, доменні поля замінено).

Лише stdlib. Заявка вважається прийнятою ТІЛЬКИ після запису в SQLite.
Продакшн-адаптери (Telegram / вебхук CRM) — з env, після запису, помилки логуються.
Безпека (OWASP Input Validation / CSRF): JSON-only, ліміт тіла, allowlist для
скінченних полів, нормалізація, довжини, honeypot, rate limit, перевірка Origin.
"""
import base64, email.utils, fcntl, hashlib, hmac, io, ipaddress, json, logging, math, os, posixpath, re, sqlite3, subprocess, sys, threading, time, unicodedata, urllib.parse, urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / 'web'
DATA = ROOT / 'data'
CONFIG = ROOT / 'config' / 'business.json'
os.umask(0o077)  # PII, logs and SQLite sidecars must not inherit permissive host modes.
DATA.mkdir(mode=0o700, exist_ok=True)
DATA.chmod(0o700)


def load_env():
    f = ROOT / '.env'
    if f.exists():
        for line in f.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())


load_env()
ENV = os.environ.get
class _OneLineFormatter(logging.Formatter):
    """Один запис = один рядок: CR/LF та інші розривачі рядка в повідомленні (зокрема з obs-fold заголовків клієнта)
    екрануються, тож клієнт не може підробити окремий запис журналу (ops/restore.py читає з нього 'lead stored id=N')."""
    BREAK = re.compile(r'[\x00-\x08\x0a-\x1f\x7f\x85\u2028\u2029]')

    def format(self, record):
        return self.BREAK.sub(lambda m: m.group().encode('unicode_escape').decode('ascii'), super().format(record))


_log_h = logging.FileHandler(DATA / 'server.log')
os.fchmod(_log_h.stream.fileno(), 0o600)
_log_h.setFormatter(_OneLineFormatter('%(asctime)s %(levelname)s %(message)s'))
logging.basicConfig(level=logging.INFO, handlers=[_log_h])
log = logging.getLogger('pbt')

def _ip_salt():
    """S10: без IP_HASH_SALT хеш IP солився константою — простір IPv4 перебирається за хвилини. Тепер — випадкова сіль,
    збережена один раз у data/.ip_salt (0600)."""
    if ENV('IP_HASH_SALT'):
        return ENV('IP_HASH_SALT')
    f = DATA / '.ip_salt'
    if not f.exists():
        fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as h:
            h.write(os.urandom(24).hex())
    return f.read_text().strip()


IP_SALT = _ip_salt()


def _ip_hash(ip):
    """Keyed pseudonymous client identifier; never write a raw address to logs."""
    return hmac.new(IP_SALT.encode(), ip.encode(), hashlib.sha256).hexdigest()[:16]


MAX_BODY = 8 * 1024
TYPES = {'rent', 'material', 'transport', 'other'}
METHODS = {'phone', 'telegram', 'viber', 'whatsapp'}

# ─── сховище ─────────────────────────────────────────────
DB = Path(ENV('LEAD_DB') or DATA / 'leads.db')
for _suffix in ('', '-wal', '-shm', '-journal'):
    _private_db_file = Path(f'{DB}{_suffix}')
    if _private_db_file.is_file():
        _private_db_file.chmod(0o600)
_db_lock = threading.Lock()


def db(timeout=10):
    c = sqlite3.connect(DB, timeout=timeout)
    try:
        # Both are per-connection, no-ops inside a transaction, and must precede any statement.
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('PRAGMA synchronous=FULL')  # HTTP 201 relies on commit durability.
        if c.execute('PRAGMA foreign_keys').fetchone()[0] != 1:
            raise sqlite3.DatabaseError('foreign_keys enforcement unavailable')
        c.execute('''CREATE TABLE IF NOT EXISTS leads(
            id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT NOT NULL, type TEXT NOT NULL,
            payload TEXT NOT NULL, ip_hash TEXT, ua TEXT, delivered TEXT)''')
    except BaseException:
        c.close()
        raise
    return c


def migrate(timeout=10):
    """Адитивна міграція (старі рядки й старі бази лишаються валідними): ключ ідемпотентності + відбиток корисного навантаження
    на заявці (унікальність — рівнем БД, частковий індекс: у старих рядків NULL) і outbox доставки — рядок на (заявка, канал).

    Atomic: SQLite DDL is transactional, so a failure leaves the previous schema intact.
    Legacy foreign-key violations are reported, never repaired or deleted: enforcement applies
    to new writes, and reconciling an old anomaly is an operator decision (ops/outbox_health.py).
    """
    c = db(timeout)
    try:
        c.execute('BEGIN IMMEDIATE')
        cols = {r[1] for r in c.execute('PRAGMA table_info(leads)')}
        for col in ('idem_key', 'payload_hash'):
            if col not in cols:
                c.execute(f'ALTER TABLE leads ADD COLUMN {col} TEXT')
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS leads_idem_key ON leads(idem_key) WHERE idem_key IS NOT NULL')
        c.execute('''CREATE TABLE IF NOT EXISTS outbox(
            id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER NOT NULL REFERENCES leads(id), channel TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0, next_at REAL NOT NULL DEFAULT 0,
            last_at REAL, last_error TEXT, delivered_at TEXT, UNIQUE(lead_id, channel))''')
        c.execute("CREATE INDEX IF NOT EXISTS outbox_due ON outbox(status, next_at)")
        c.execute("""CREATE TABLE IF NOT EXISTS runtime_heartbeat(
            name TEXT PRIMARY KEY, observed_at REAL NOT NULL)""")
        c.commit()
        violations = {}
        for table, *_ in c.execute('PRAGMA foreign_key_check'):
            violations[table] = violations.get(table, 0) + 1
        for table, count in sorted(violations.items()):
            log.error('legacy foreign key violations=%s table=%s', count, table)
    except BaseException:
        c.rollback()
        raise
    finally:
        c.close()


_schema_ok = threading.Event()   # OPS-3: міграція пройшла; до того /api/lead → 503, health → db false


def _try_migrate(timeout):
    try:
        with _db_lock:
            migrate(timeout)
        _schema_ok.set(); return True
    except sqlite3.Error as e:  # Includes a corrupt file: static site stays up, /api/lead answers 503.
        log.error('migrate failed err=%s %s', type(e).__name__, e); return False


def migrate_retry_worker():
    while not _try_migrate(10):
        time.sleep(5)


# OPS-3: лок БД на старті не валить процес (раніше — OperationalError на імпорті, лягала й статика): обмежені спроби,
# далі сервер стартує, а міграція повторюється у фоні (main).
for _i in range(int(ENV('MIGRATE_BOOT_ATTEMPTS') or 3)):
    if _try_migrate(2):
        break
    time.sleep(0.5)

# ─── rate limit на IP: усі запити (захист від перебору) і прийняті заявки ───
_hits, _hits_lock = {}, threading.RLock()
# One identity per client, independently of its three quota buckets; insertion order = least recently seen first.
_active_ips = {}
RATE_IP_CAP = int(ENV('RATE_IP_CAP') or 8192)
if RATE_IP_CAP < 1:
    raise ValueError('RATE_IP_CAP must be positive')
# Keep evicted quota histories in a second bounded tier.  At its capacity a
# new identity is refused until an existing history expires; otherwise an
# attacker could reset another client's quota merely by rotating identities.
RATE_OVERFLOW_CAP = int(ENV('RATE_OVERFLOW_CAP') or 32768)
if RATE_OVERFLOW_CAP < 1:
    raise ValueError('RATE_OVERFLOW_CAP must be positive')
_overflow = {}
LIMITS = {'any': (int(ENV('RATE_ANY_10MIN') or 60), 600), 'lead': (int(ENV('RATE_LEAD_10MIN') or 5), 600),
          'lead_day': (int(ENV('RATE_LEAD_DAY') or 30), 86400)}
_BUCKETS = tuple(LIMITS)


_last_prune = [0.0]
_last_pressure_prune = [0.0]


def _prune(now, force=False):
    """S3: словник лімітів не росте без меж — ключі з порожнім вікном видаляються (не частіше ніж раз на хвилину)."""
    if not force and now - _last_prune[0] < 60:
        return
    _last_prune[0] = now
    for key in [k for k, ts in _hits.items() if not ts or now - ts[-1] >= LIMITS[k[1]][1]]:
        del _hits[key]
    live = {ip for ip, _ in _hits}
    for ip in [ip for ip in _active_ips if ip not in live]:
        del _active_ips[ip]
    for ip, values in list(_overflow.items()):
        kept = tuple(ts if ts and now - ts[-1] < LIMITS[b][1] else None
                     for b, ts in zip(_BUCKETS, values))
        if any(kept):
            _overflow[ip] = kept
        else:
            del _overflow[ip]


def rate_identity(ip):
    """IPv6 clients are limited per /64: one subscriber routinely owns the whole prefix, so per-address keys would
    let a single sender mint unlimited identities. IPv4 (and anything unparsable) stays per address."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if addr.version == 6:
        if addr.ipv4_mapped is not None:
            return str(addr.ipv4_mapped)
        return str(ipaddress.ip_network(f'{addr}/64', strict=False))
    return str(addr)


def _history(ip, bucket):
    if ip in _overflow:
        return _overflow[ip][_BUCKETS.index(bucket)] or []
    return _hits.get((ip, bucket), [])


def _touch(ip, now):
    """Move an identity to the hot tier without ever discarding live quotas."""
    if ip in _active_ips:
        _active_ips.pop(ip)
        _active_ips[ip] = None
        return True
    restored = _overflow.pop(ip, None)
    if len(_active_ips) >= RATE_IP_CAP:
        if len(_overflow) >= RATE_OVERFLOW_CAP and now - _last_pressure_prune[0] >= 1:
            _last_pressure_prune[0] = now
            _prune(now, force=True)
        if len(_active_ips) >= RATE_IP_CAP and len(_overflow) >= RATE_OVERFLOW_CAP:
            return False
        if len(_active_ips) >= RATE_IP_CAP:
            old = next(iter(_active_ips))
            del _active_ips[old]
            values = tuple(_hits.pop((old, b), None) for b in _BUCKETS)
            if any(values):
                _overflow[old] = values
    _active_ips[ip] = None
    if restored is not None:
        for b, values in zip(_BUCKETS, restored):
            if values:
                _hits[(ip, b)] = values
    return True


def rate_ok(ip, *buckets, commit=True):
    ip = rate_identity(ip)
    with _hits_lock:
        # Quota windows measure elapsed time, independent of wall-clock steps.
        # Read after acquiring the lock to preserve timestamp ordering.
        now = time.monotonic()
        _prune(now)
        for b in buckets:
            lim, win = LIMITS[b]
            if len([t for t in _history(ip, b) if now - t < win]) >= lim:
                return False
        if commit or (ip not in _active_ips and ip not in _overflow):
            if not _touch(ip, now):
                return False
        elif ip in _overflow:
            if not _touch(ip, now):
                return False
        if commit:
            for b in buckets:
                _hits[(ip, b)] = [t for t in _hits.get((ip, b), []) if now - t < LIMITS[b][1]] + [now]
        return True


def rate_commit(ip, *buckets):
    """OPS-4: списати квоту після успішного запису (без повторної перевірки — заявка вже прийнята)."""
    ip = rate_identity(ip)
    with _hits_lock:
        now = time.monotonic()
        if not _touch(ip, now):
            raise RuntimeError('quota identity was not reserved before durable write')
        for b in buckets:
            _hits[(ip, b)] = [t for t in _hits.get((ip, b), []) if now - t < LIMITS[b][1]] + [now]


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
    if not date_allowed(s):
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


# ─── продакшн-адаптери: сталий outbox (SQLite) ───────────
# Заявка приймається по коміту в SQLite; доставка (Telegram / вебхук) — окремий потік, поза запитом: рядок outbox на канал,
# повтори з обмеженою експоненційною затримкою, постійні помилки (4xx, крім 408/429) не повторюються. Перезапуск не губить
# незавершену доставку (стан у БД). Семантика — «щонайменше раз»: падіння між відправкою й записом статусу дасть повтор
# (вебхук несе id заявки для ідемпотентного прийому).
DELIVERY_TIMEOUT = float(ENV('DELIVERY_TIMEOUT') or 8)
if not math.isfinite(DELIVERY_TIMEOUT) or not 0.1 <= DELIVERY_TIMEOUT <= 120:
    raise ValueError('DELIVERY_TIMEOUT must be finite and between 0.1 and 120 seconds')
DELIVERY_CONCURRENCY = int(ENV('DELIVERY_CONCURRENCY') or 4)
if not 1 <= DELIVERY_CONCURRENCY <= 8:
    raise ValueError('DELIVERY_CONCURRENCY must be between 1 and 8')
DELIVERY_MAX_ATTEMPTS = int(ENV('DELIVERY_MAX_ATTEMPTS') or 8)
if not 1 <= DELIVERY_MAX_ATTEMPTS <= 64:
    raise ValueError('DELIVERY_MAX_ATTEMPTS must be between 1 and 64')
DELIVERY_BACKOFF_S = float(ENV('DELIVERY_BACKOFF_S') or 30)        # 30 с · 2^(n−1), стеля — 6 год
if not math.isfinite(DELIVERY_BACKOFF_S) or not 0.001 <= DELIVERY_BACKOFF_S <= 604800:
    raise ValueError('DELIVERY_BACKOFF_S must be finite and between 0.001 and 604800')
DELIVERY_BACKOFF_MAX_S = 6 * 3600
DELIVERY_POLL_S = float(ENV('DELIVERY_POLL_S') or 30)
if not math.isfinite(DELIVERY_POLL_S) or not 0.01 <= DELIVERY_POLL_S <= 300:
    raise ValueError('DELIVERY_POLL_S must be finite and between 0.01 and 300')
DELIVERY_HEARTBEAT_INTERVAL_S = float(ENV('DELIVERY_HEARTBEAT_INTERVAL_S') or 15)
if not 1 <= DELIVERY_HEARTBEAT_INTERVAL_S <= 60:
    raise ValueError('DELIVERY_HEARTBEAT_INTERVAL_S must be between 1 and 60')
HEALTH_MIN_FREE_MB = float(ENV('HEALTH_MIN_FREE_MB') or 50)
if not math.isfinite(HEALTH_MIN_FREE_MB) or HEALTH_MIN_FREE_MB < 0:
    raise ValueError('HEALTH_MIN_FREE_MB must be finite and non-negative')
TELEGRAM_API = ENV('TELEGRAM_API_BASE') or 'https://api.telegram.org'
_wake = threading.Event()


class PermanentDeliveryError(Exception):
    pass


def channels():
    out = []
    if ENV('TELEGRAM_BOT_TOKEN') and ENV('TELEGRAM_CHAT_ID'):
        out.append('telegram')
    if ENV('LEAD_WEBHOOK_URL'):
        if ENV('LEAD_WEBHOOK_SECRET'):
            out.append('webhook')
        else:                                   # S11: без секрету підпис HMAC з порожнім ключем нічого не доводить
            log.error('webhook skipped: LEAD_WEBHOOK_SECRET not set')
    return out


class TransientDeliveryError(Exception):
    pass


_DELIVERY_CHILD = ROOT / 'server' / 'delivery_transport.py'
_DELIVERY_CHILD_ENV = {
    'PATH', 'SSL_CERT_FILE', 'SSL_CERT_DIR',
    'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY',
    'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy',
}


def _safe_outbound_url(url):
    """Never transmit accepted lead PII or Telegram tokens over remote plaintext.

    Local synthetic and same-host adapters may use loopback HTTP. All other
    endpoints require TLS and cannot carry embedded URI credentials.
    """
    try:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            return False
        if parsed.username is not None or parsed.password is not None:
            return False
        _ = parsed.port  # Reject malformed numeric ports.
        if parsed.scheme == 'https':
            return True
        if parsed.hostname == 'localhost':
            return True
        return ipaddress.ip_address(parsed.hostname).is_loopback
    except (ValueError, TypeError):
        return False


# Invalid external endpoints are a startup error, not silently omitted delivery.
for _url in (ENV('LEAD_WEBHOOK_URL'), ENV('TELEGRAM_API_BASE')):
    if _url and not _safe_outbound_url(_url):
        raise ValueError('insecure outbound delivery URL: remote HTTPS required')


def send(channel, lead_id, data):
    """One *absolute-deadline* outbound attempt; no unkillable socket threads.

    The Linux child owns DNS, TLS and reading response headers. Parent's
    communicate(timeout) kills and reaps it on deadline, preserving durable
    at-least-once retries even if the receiver already accepted the request.
    Payload/Telegram credentials travel via stdin, never argv or logs.
    """
    if channel == 'telegram':
        text = f"Заявка PBT-{lead_id:06d}\n" + '\n'.join(f"{k}: {v}" for k, v in data.items() if v not in (None, ''))
        # Telegram Bot API accepts application/json. UTF-8 avoids 12-byte
        # percent-encoding per astral emoji and remains below the child 16-KiB
        # body limit for a 4000-character message (<=16000 UTF-8 bytes).
        body = json.dumps({'chat_id': ENV('TELEGRAM_CHAT_ID'), 'text': text[:4000]},
                          ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        url = f"{TELEGRAM_API}/bot{ENV('TELEGRAM_BOT_TOKEN')}/sendMessage"
        headers = {'Content-Type': 'application/json'}
    elif channel == 'webhook':
        body = json.dumps({'id': lead_id, **data}, ensure_ascii=False).encode()
        signature = hmac.new(ENV('LEAD_WEBHOOK_SECRET').encode(), body, hashlib.sha256).hexdigest()
        url = ENV('LEAD_WEBHOOK_URL')
        headers = {'Content-Type': 'application/json', 'X-PBT-Signature': signature}
    else:
        raise PermanentDeliveryError(f'unknown channel {channel}')

    if not _safe_outbound_url(url):
        raise PermanentDeliveryError('insecure outbound delivery URL')

    wire = json.dumps({
        'url': url, 'body_b64': base64.b64encode(body).decode('ascii'),
        'headers': headers, 'socket_timeout_s': DELIVERY_TIMEOUT,
    }, ensure_ascii=True, separators=(',', ':')).encode('utf-8')
    if len(wire) > 65536:
        raise PermanentDeliveryError('delivery payload too large')

    env = {k: v for k, v in os.environ.items() if k in _DELIVERY_CHILD_ENV}
    env['PBT_PARENT_PID'] = str(os.getpid())
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    try:
        child = subprocess.Popen(
            [sys.executable, str(_DELIVERY_CHILD)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env=env, close_fds=True)
    except OSError as exc:
        raise TransientDeliveryError(type(exc).__name__) from None
    try:
        reply, _ = child.communicate(wire, timeout=DELIVERY_TIMEOUT)
    except subprocess.TimeoutExpired:
        child.kill()
        child.communicate()  # Reap; do not strand a process or an executor slot.
        raise TransientDeliveryError('outbound_total_deadline') from None

    status = reply.decode('ascii', errors='replace').strip()
    if child.returncode == 0 and not status:
        return
    if child.returncode == 10 and re.fullmatch(r'HTTP 4\d{2}', status):
        raise PermanentDeliveryError(status)
    if child.returncode == 11 and re.fullmatch(r'(?:HTTP [1-5]\d{2}|[A-Za-z][A-Za-z0-9_]{0,39})', status):
        raise TransientDeliveryError(status)
    raise TransientDeliveryError('delivery_child_failure')


def _attempt_delivery(row):
    """Network I/O only: no SQLite access from sender threads."""
    _, lead_id, channel, _, payload = row
    try:
        send(channel, lead_id, json.loads(payload))
        return None, False
    except PermanentDeliveryError as e:
        return str(e), True
    except TransientDeliveryError as e:
        return str(e), False
    except Exception as e:  # noqa: BLE001
        return type(e).__name__ + (f' {e.code}' if isinstance(e, urllib.error.HTTPError) else ''), False


def _completed_with_heartbeat(tasks, heartbeat):
    """Yield completed network futures and refresh worker activity while waiting.

    No SQLite lock is held while waiting. The callback is called on completion
    and on bounded timeout; heartbeat means worker activity, never CRM success.
    """
    if heartbeat is None:
        yield from as_completed(tasks)
        return
    pending = set(tasks)
    while pending:
        done, pending = wait(pending, timeout=DELIVERY_HEARTBEAT_INTERVAL_S,
                             return_when=FIRST_COMPLETED)
        heartbeat()
        yield from done


def deliver_due(now=None, heartbeat=None):
    """One bounded outbox batch; apply results as they complete (at-least-once after crash)."""
    with _db_lock:
        c = db()
        rows = c.execute("SELECT o.id, o.lead_id, o.channel, o.attempts, l.payload FROM outbox o JOIN leads l ON l.id = o.lead_id "
                         "WHERE o.status = 'pending' AND o.next_at <= ? ORDER BY o.id LIMIT 50", (now or time.time(),)).fetchall()
        c.close()
    if not rows:
        return 0
    # At most 50 queued and at most 8 in-flight network requests. The sole
    # delivery worker owns this batch; never hold _db_lock across network I/O.
    with ThreadPoolExecutor(max_workers=DELIVERY_CONCURRENCY, thread_name_prefix='pbt-delivery') as executor:
        tasks = {executor.submit(_attempt_delivery, row): row for row in rows}
        for task in _completed_with_heartbeat(tasks, heartbeat):
            oid, lead_id, ch, att, _ = tasks[task]
            err, permanent = task.result()
            att += 1
            t = time.time()
            with _db_lock:
                c = db()
                try:
                    if err is None:
                        c.execute("UPDATE outbox SET status='delivered', attempts=?, last_at=?, last_error=NULL, delivered_at=? WHERE id=?",
                                  (att, t, datetime.now(timezone.utc).isoformat(), oid))
                        sent = [r[0] for r in c.execute("SELECT channel FROM outbox WHERE lead_id=? AND status='delivered' ORDER BY id", (lead_id,))]
                        c.execute('UPDATE leads SET delivered=? WHERE id=?', (','.join(sent), lead_id))
                        log.info('delivery ok lead=%s channel=%s attempt=%s', lead_id, ch, att)
                    elif permanent or att >= DELIVERY_MAX_ATTEMPTS:
                        c.execute("UPDATE outbox SET status='failed', attempts=?, last_at=?, last_error=? WHERE id=?", (att, t, err, oid))
                        log.error('delivery FAILED lead=%s channel=%s attempts=%s err=%s', lead_id, ch, att, err)
                    else:
                        nxt = t + min(DELIVERY_BACKOFF_S * 2 ** (att - 1), DELIVERY_BACKOFF_MAX_S)
                        c.execute('UPDATE outbox SET attempts=?, last_at=?, last_error=?, next_at=? WHERE id=?', (att, t, err, nxt, oid))
                        log.warning('delivery retry lead=%s channel=%s attempt=%s err=%s', lead_id, ch, att, err)
                    c.commit()
                finally:
                    c.close()
    return len(rows)


def _record_worker_heartbeat():
    """Durable *thread activity* marker; never misrepresent as downstream success."""
    with _db_lock:
        c = db()
        try:
            c.execute("""INSERT INTO runtime_heartbeat(name, observed_at)
                         VALUES('delivery', ?)
                         ON CONFLICT(name) DO UPDATE SET observed_at=excluded.observed_at""",
                      (time.time(),))
            c.commit()
        finally:
            c.close()


def delivery_worker():
    last_heartbeat = float('-inf')

    def heartbeat_if_due():
        nonlocal last_heartbeat
        if time.monotonic() - last_heartbeat < DELIVERY_HEARTBEAT_INTERVAL_S:
            return
        try:
            _record_worker_heartbeat()
            last_heartbeat = time.monotonic()
        except Exception as e:  # noqa: BLE001
            log.error('delivery heartbeat error %s', type(e).__name__)

    while True:
        heartbeat_if_due()
        try:
            # Maintain liveness through each 50-row batch and continuously
            # draining backlog. Never wait for all outbound futures to finish.
            while deliver_due(heartbeat=heartbeat_if_due) == 50:
                heartbeat_if_due()
        except Exception as e:  # noqa: BLE001
            log.error('delivery worker error %s', type(e).__name__)
        heartbeat_if_due()
        # Wake often enough to record heartbeat even without new requests.
        _wake.wait(min(DELIVERY_POLL_S, DELIVERY_HEARTBEAT_INTERVAL_S))
        _wake.clear()


def public_config():
    try:
        c = json.loads(CONFIG.read_text(encoding='utf-8'))
    except Exception:  # noqa: BLE001
        return {}
    c.pop('_status', None)
    return c


# ─── HTTP ────────────────────────────────────────────────
def _inline_script_hashes():
    """S5: CSP без 'unsafe-inline' для скриптів — дозволено лише точні вбудовані скрипти сторінок (sha256)."""
    import base64
    out = set()
    for f in WEB.glob('*.html'):
        for m in re.finditer(r'<script>(.*?)</script>', f.read_text(encoding='utf-8'), re.S):
            out.add("'sha256-" + base64.b64encode(hashlib.sha256(m.group(1).encode()).digest()).decode() + "'")
    return ' '.join(sorted(out))


WEB_REAL = os.path.realpath(WEB)


def in_web(path):
    """Реальний (після розіменування symlink) шлях — сам web/ або його нащадок. Порівняння з роздільником: 'web_x' не є нащадком 'web'."""
    real = os.path.realpath(path)
    return real == WEB_REAL or real.startswith(WEB_REAL + os.sep)


SEC_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'X-Frame-Options': 'DENY',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
    'Content-Security-Policy': "default-src 'self'; img-src 'self' data:; media-src 'self'; style-src 'self' 'unsafe-inline'; "
                               f"script-src 'self' {_inline_script_hashes()}; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
}


class _HeaderDeadlineReader(io.RawIOBase):
    """SEC-1: сирий читач сокета. Поки йде читання рядка запиту+заголовків, таймаут КОЖНОГО recv = min(timeout, залишок
    абсолютного бюджету) — крапля байта не продовжує життя запиту (timeout сокета скидався на кожному байті)."""
    def __init__(self, h):
        self.h = h

    def readable(self):
        return True

    def readinto(self, b):
        h = self.h
        header_deadline = h._hdr_deadline
        body_deadline = h._body_deadline if header_deadline is None else None
        deadline = header_deadline if header_deadline is not None else body_deadline
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if header_deadline is not None:
                    h._hdr_expired = True
                raise TimeoutError('absolute request read deadline')
            h.connection.settimeout(min(h.timeout, remaining))
        try:
            n = h.connection.recv_into(b)
        except TimeoutError:
            if header_deadline is not None:
                h._hdr_expired = True
            raise
        if header_deadline is not None:
            h._hdr_bytes += n
        return n


class _Slice(io.RawIOBase):
    """Читає не більше n байтів із відкритого файлу — тіло 206 для copyfile()."""
    def __init__(self, f, n):
        self.f, self.left = f, n

    def readable(self):
        return True

    def read(self, size=-1):
        if self.left <= 0:
            return b''
        size = self.left if size is None or size < 0 else min(size, self.left)
        b = self.f.read(size); self.left -= len(b)
        return b

    def close(self):
        self.f.close(); super().close()


class Handler(SimpleHTTPRequestHandler):
    server_version = 'pbt'
    sys_version = ''
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.webp': 'image/webp', '.avif': 'image/avif',
                      '.woff2': 'font/woff2', '.json': 'application/json', '.webm': 'video/webm', '.mp4': 'video/mp4',
                      '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml'}

    timeout = float(ENV('REQUEST_TIMEOUT') or 20)   # S7: bounded per-socket inactivity
    header_timeout = float(ENV('HEADER_TIMEOUT') or 10)   # SEC-1: absolute total header budget
    body_timeout = float(ENV('REQUEST_BODY_DEADLINE') or 10)  # R1: absolute body budget
    if not math.isfinite(timeout) or not 0.1 <= timeout <= 120:
        raise ValueError('REQUEST_TIMEOUT must be finite and between 0.1 and 120')
    if not math.isfinite(header_timeout) or not 0.1 <= header_timeout <= 60:
        raise ValueError('HEADER_TIMEOUT must be finite and between 0.1 and 60')
    if not 0.1 <= body_timeout <= 60:
        raise ValueError('REQUEST_BODY_DEADLINE must be between 0.1 and 60 seconds')
    _hdr_deadline = None
    _body_deadline = None

    def setup(self):
        super().setup()
        self.rfile = io.BufferedReader(_HeaderDeadlineReader(self))

    def handle_one_request(self):
        self._hdr_deadline, self._hdr_expired, self._hdr_bytes = time.monotonic() + self.header_timeout, False, 0
        try:
            super().handle_one_request()      # stdlib ковтає TimeoutError і мовчки закриває з'єднання
        finally:
            self._disarm()
        if self._hdr_expired and self._hdr_bytes:   # почав запит, не встиг за бюджет → 408 (без байтів — тихе закриття, як було)
            self.close_connection = True
            for a, v in (('requestline', ''), ('command', None)):
                if not hasattr(self, a):
                    setattr(self, a, v)
            try:
                self.send_error(HTTPStatus.REQUEST_TIMEOUT)
                self.wfile.flush()
            except OSError:
                pass

    def _disarm(self):
        if self._hdr_deadline is not None:
            self._hdr_deadline = None
            try:
                self.connection.settimeout(self.timeout)
            except OSError:
                pass

    def parse_request(self):
        ok = super().parse_request()
        self._disarm()                        # тіло (POST) читається вже з поштучним timeout, не з бюджетом заголовків
        return ok

    def send_response_only(self, code, message=None):
        self._status = code                   # SEC-3: Cache-Control залежить від статусу
        super().send_response_only(code, message)

    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(WEB), **k)

    def send_head(self):
        """S13: статика — лише файли, чий РЕАЛЬНИЙ шлях усередині web/. SimpleHTTPRequestHandler іде за символьними посиланнями:
        web/x → ../secret віддавав зовнішній файл (200). Тепер — 404 (без розкриття структури ФС). Діє для GET і HEAD."""
        if not in_web(self.translate_path(self.path)):
            self.send_error(404)
            return None
        if self.url_path().startswith('/media/'):
            return self.send_media()
        return super().send_head()

    RANGE = re.compile(r'bytes=(\d*)-(\d*)$', re.I)            # одиниця діапазону нечутлива до регістру (RFC 9110 §14.1)

    def url_path(self):
        """Нормалізований шлях запиту (як його бачить translate_path): /media/../js/x.js → /js/x.js. Гілки статики й кешу — лише за ним."""
        p = posixpath.normpath(urllib.parse.unquote((getattr(self, 'path', None) or '').split('?', 1)[0].split('#', 1)[0]))
        return '/' if p in ('.', '//') else p

    def not_modified(self, mtime):
        """If-Modified-Since як ДАТА (RFC 9110 §13.1.3); нерозбірна — ігнорується."""
        ims = self.headers.get('If-Modified-Since')
        if not ims or self.headers.get('If-None-Match'):
            return False
        try:
            return int(mtime) <= email.utils.parsedate_to_datetime(ims).timestamp()
        except (TypeError, ValueError, IndexError, OverflowError):
            return False

    def send_media(self):
        """P14: медіа з HTTP Range (RFC 9110 §14). Safari/iOS не відтворює mp4 без 206; Chromium без нього не перемотує
        (кліп після seek скидається на 0). Один діапазон; кілька, зламаний або If-Range від іншої версії → увесь файл 200;
        за межами файлу → 416. Тіло — зріз файлу без читання в пам'ять."""
        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            self.send_error(404)
            return None
        f = open(path, 'rb')
        try:
            st = os.fstat(f.fileno()); size = st.st_size
            lm = self.date_time_string(int(st.st_mtime))
            if self.not_modified(st.st_mtime):                   # §13.2.2: If-Modified-Since перевіряється ДО Range
                f.close(); self.send_response(304); self.send_header('Last-Modified', lm); self.end_headers(); return None
            m = self.RANGE.match((self.headers.get('Range') or '').strip())
            if_range = self.headers.get('If-Range')
            if m and (m.group(1) or m.group(2)) and (not if_range or if_range == lm):
                a, b = m.group(1), m.group(2)
                if a:
                    start, end = int(a), min(int(b), size - 1) if b else size - 1
                else:                                           # суфікс: останні N байтів
                    start, end = max(size - int(b), 0), size - 1
                if a and b and int(b) < int(a):                 # синтаксично невалідний (5-3) → ігнорувати Range, увесь файл
                    start, end = None, None
                elif start >= size or start > end:
                    f.close()
                    self.send_response(416); self.send_header('Content-Range', f'bytes */{size}')
                    self.send_header('Content-Length', '0'); self.end_headers(); return None
            if m and (m.group(1) or m.group(2)) and (not if_range or if_range == lm) and start is not None:
                f.seek(start)
                self.send_response(206)
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                length = end - start + 1
            else:
                self.send_response(200)
                length = size
            self.send_header('Content-Type', self.guess_type(path))
            self.send_header('Content-Length', str(length))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Last-Modified', lm)
            self.end_headers()
            return _Slice(f, length)
        except Exception:
            f.close()
            raise

    def list_directory(self, path):   # S4: без лістингу каталогів (/media/ тощо)
        self.send_error(404)
        return None

    def client_ip(self):
        """S1: за локальним реверс-проксі (Tailscale Funnel / serve) усі з'єднання йдуть з 127.0.0.1 — ліміти ставали спільними
        для всього світу. Довіряємо X-Forwarded-For ЛИШЕ від loopback-піра і беремо крайній правий запис (доданий проксі)."""
        peer = self.client_address[0]
        if self.behind_trusted_proxy():
            # All header lines: a proxy may append its own line rather than merge into the client's.
            lines = (getattr(self, 'headers', None) and self.headers.get_all('X-Forwarded-For')) or []
            xff = [p.strip() for line in lines for p in line.split(',') if p.strip()]
            if xff and re.fullmatch(r'[0-9A-Fa-f:.]{2,45}', xff[-1]):
                return xff[-1]
        return peer

    def behind_trusted_proxy(self):
        """S14: заголовки проксі (X-Forwarded-For/-Proto) довіряються лише за явного TRUST_PROXY=1 (конфіг розгортання: ops/systemd,
        Tailscale Funnel) і лише від loopback-піра. Раніше довіра була увімкнена кодом за замовчуванням → без проксі клієнт сам обирав
        собі ідентичність для лімітів."""
        return self.client_address[0] in ('127.0.0.1', '::1') and (ENV('TRUST_PROXY') or '0') == '1'

    def log_message(self, fmt, *args):
        # Do not persist query-string PII, URLs, Origin headers or raw peer IP.
        # Only log bounded, server-derived metadata and a keyed IP pseudonym.
        status = str(args[1]) if fmt == '"%s" %s %s' and len(args) == 3 else ''
        if not re.fullmatch(r'[1-5][0-9]{2}', status):
            status = 'event'
        method = self.command if getattr(self, 'command', None) in ('GET', 'HEAD', 'POST', 'OPTIONS') else 'OTHER'
        log.info('http client_hash=%s method=%s status=%s', _ip_hash(self.client_ip()), method, status)

    def end_headers(self):
        for k, v in SEC_HEADERS.items():
            self.send_header(k, v)
        if getattr(self, 'headers', None) and self.behind_trusted_proxy() and self.headers.get('X-Forwarded-Proto') == 'https':   # S6: HSTS лише коли запит прийшов по HTTPS
            self.send_header('Strict-Transport-Security', 'max-age=15552000')
        p = self.url_path()   # SEC-2: помилка розбору — path ще не присвоєно (url_path терпить); нормалізовано — /media/../js не кешується тиждень
        if p.startswith(('/media/', '/fonts/')) and getattr(self, '_status', None) in (200, 206, 304):   # SEC-3: 404 не кешується тиждень
            self.send_header('Cache-Control', 'public, max-age=604800')
        elif not p.startswith('/api/'):
            self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def send_json(self, code, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)

    def send_error(self, code, message=None, explain=None):
        if getattr(self, 'request_version', None) in (None, 'HTTP/0.9'):   # SEC-2: невалідна версія лишає 0.9 → помилка без статус-рядка
            self.request_version = 'HTTP/1.0'
        if code == 404 and (WEB / '404.html').exists():
            raw = (WEB / '404.html').read_bytes()
            self.send_response(404)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            if getattr(self, 'command', None) != 'HEAD':   # HEAD — без тіла (RFC 9110 §9.3.2)
                self.wfile.write(raw)
            return
        super().send_error(code, message, explain)

    GZIP_TYPES = {'.css', '.js', '.html', '.json', '.svg', '.txt'}
    _gz_cache = {}

    def serve_gzip(self):
        """P12: текстові ресурси стиснуті gzip (CSS 84 КБ, JS 108 КБ блокували рендер на повільній мережі). Кеш за (шлях, mtime, розмір);
        ETag → 304; Vary: Accept-Encoding. Лише файли всередині web/ (той самий translate_path, що й для статики)."""
        if 'gzip' not in (self.headers.get('Accept-Encoding') or ''):
            return False
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            path = os.path.join(path, 'index.html')
        ext = os.path.splitext(path)[1].lower()
        if ext not in self.GZIP_TYPES or not os.path.isfile(path) or not in_web(path):
            return False
        st = os.stat(path); key = (path, st.st_mtime_ns, st.st_size)
        body = self._gz_cache.get(key)
        if body is None:
            import gzip
            with open(path, 'rb') as f:
                body = gzip.compress(f.read(), 6, mtime=0)
            self._gz_cache.clear() if len(self._gz_cache) > 256 else None
            self._gz_cache[key] = body
        etag = f'"{st.st_mtime_ns:x}-{st.st_size:x}-gz"'
        if self.headers.get('If-None-Match') == etag:
            self.send_response(304); self.send_header('ETag', etag); self.send_header('Vary', 'Accept-Encoding'); self.end_headers(); return True
        self.send_response(200)
        self.send_header('Content-Type', self.guess_type(path) + ('; charset=utf-8' if ext in ('.html', '.css', '.js', '.txt') else ''))
        self.send_header('Content-Encoding', 'gzip'); self.send_header('Vary', 'Accept-Encoding')
        self.send_header('Content-Length', str(len(body))); self.send_header('ETag', etag)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)
        return True

    def do_GET(self):
        if self.path.split('?')[0] == '/api/config':
            return self.send_json(200, public_config())
        if self.path.split('?')[0] == '/api/health':
            return self.health()
        if self.serve_gzip():
            return
        return super().do_GET()

    def health(self):
        """O1: здоров'я = сховище заявок справді працює (читання й запис у транзакції з відкатом) і на диску є місце.
        Раніше /api/health завжди відповідав {ok: true} — сторож не бачив би зламаної бази."""
        checks = {}
        try:
            with _db_lock:
                c = db(); c.execute('BEGIN'); c.execute("INSERT INTO leads(created,type,payload) VALUES('health','health','{}')")
                c.execute('ROLLBACK'); checks['db'] = c.execute('SELECT count(*) FROM leads').fetchone()[0] >= 0 and _schema_ok.is_set(); c.close()
        except Exception as e:  # noqa: BLE001
            checks['db'] = False; log.error('health: db %s', type(e).__name__)
        st = os.statvfs(DB.parent); checks['disk'] = st.f_bavail * st.f_frsize > HEALTH_MIN_FREE_MB * 1024 * 1024
        ok = all(checks.values())
        return self.send_json(200 if ok else 503, {'ok': ok, **checks})

    def origin_ok(self):
        origin = self.headers.get('Origin')
        if not origin:
            return False
        allowed = {o.strip() for o in (ENV('ALLOWED_ORIGINS') or '').split(',') if o.strip()}
        host = self.headers.get('Host', '')
        own = {f'http://{host}', f'https://{host}'}
        return origin in own or origin in allowed

    def do_POST(self):
        if self.path.split('?')[0] != '/api/lead':
            return self.send_json(404, {'ok': False, 'error': 'not_found'})
        ip = self.client_ip()
        if not self.origin_ok():
            log.warning('lead rejected: origin ip_hash=%s', _ip_hash(ip))
            return self.send_json(403, {'ok': False, 'error': 'origin'})
        # Parsed media type (case-insensitive, RFC 9110 §8.3.1), never a substring of the raw header.
        if self.headers.get('Content-Type') is None or self.headers.get_content_type() != 'application/json':
            return self.send_json(415, {'ok': False, 'error': 'content_type'})
        # Ambiguous framing is rejected before any body byte or quota is consumed (RFC 9112 §6.3).
        lengths = self.headers.get_all('Content-Length') or []
        if self.headers.get('Transfer-Encoding') is not None or len(lengths) > 1 or (
                lengths and not re.fullmatch(r'[0-9]{1,10}', lengths[0].strip())):
            self.close_connection = True
            return self.send_json(400, {'ok': False, 'error': 'framing'})
        n = int(lengths[0]) if lengths else 0
        if n <= 0 or n > MAX_BODY:
            return self.send_json(413, {'ok': False, 'error': 'size'})
        if not rate_ok(ip, 'any'):
            return self.rate_limited(ip)
        self._body_deadline = time.monotonic() + self.body_timeout
        try:
            raw = self.rfile.read(n)
        except TimeoutError:
            # Абсолютний час вичерпано: ніколи не приймати недочитаний JSON.
            self.close_connection = True
            return self.send_json(408, {'ok': False, 'error': 'request_timeout'})
        except Exception:  # noqa: BLE001
            self.close_connection = True
            return self.send_json(400, {'ok': False, 'error': 'json'})
        finally:
            self._body_deadline = None
            try:
                self.connection.settimeout(self.timeout)
            except OSError:
                pass
        if len(raw) != n:
            self.close_connection = True
            return self.send_json(400, {'ok': False, 'error': 'json'})
        try:
            body = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            return self.send_json(400, {'ok': False, 'error': 'json'})
        try:
            data, err = validate(body)
        except Exception as e:  # noqa: BLE001 — запобіжник: жоден вхід не валить обробник (S12)
            log.error('lead validation crashed ip_hash=%s err=%s', _ip_hash(ip), type(e).__name__)
            return self.send_json(400, {'ok': False, 'error': 'validation'})
        if err.get('_') == 'spam':
            log.warning('lead dropped: honeypot ip_hash=%s', _ip_hash(ip))
            return self.send_json(200, {'ok': True, 'ref': 'PBT-000000'})  # тиха відмова ботам
        if err:
            return self.send_json(422, {'ok': False, 'error': 'validation', 'fields': err})
        idem = self.headers.get('Idempotency-Key')
        if idem is not None and not re.fullmatch(r'[A-Za-z0-9_-]{8,100}', idem):
            return self.send_json(400, {'ok': False, 'error': 'idempotency_key'})
        ph = hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if not _schema_ok.is_set():
            log.error('lead storage unavailable: schema not migrated ip_hash=%s', _ip_hash(ip))
            return self.send_json(503, {'ok': False, 'error': 'storage'})
        if idem:
            replay = self.idem_replay(idem, ph)
            if replay:
                return replay()
        # Fast-reject only unkeyed leads. A keyed caller can observe its
        # key absent, then another caller can commit that same key and exhaust
        # quota before this caller reaches the old fast-path check. Keyed
        # requests must reach the lock-scoped replay/conflict check first,
        # preserving 201 replay and 409 conflict instead of a false 429.
        if not idem and not rate_ok(ip, 'lead', 'lead_day', commit=False):
            return self.rate_limited(ip)
        ip_hash = _ip_hash(ip)
        chans = channels()
        quota_raced = False
        existing = None
        lead_id = None
        try:
            # Keep the quota reservation stable across the durable insert and
            # its charge, even while other IPs concurrently fill both tiers.
            with _db_lock, _hits_lock:
                c = db()
                try:
                    c.execute('BEGIN IMMEDIATE')
                    # A matching request may have committed since idem_replay().
                    # Recheck inside the same lock, before enforcing the quota.
                    if idem:
                        existing = c.execute(
                            'SELECT id, payload_hash FROM leads WHERE idem_key=?',
                            (idem,)).fetchone()
                    if existing is None:
                        # Check + SQLite commit + quota charge are serialized.
                        # Previously these were separate critical sections:
                        # simultaneous new keys could all pass a quota of one.
                        if not rate_ok(ip, 'lead', 'lead_day', commit=False):
                            quota_raced = True
                        else:
                            cur = c.execute(
                                'INSERT INTO leads(created,type,payload,ip_hash,ua,idem_key,payload_hash) '
                                'VALUES(?,?,?,?,?,?,?)',
                                (datetime.now(timezone.utc).isoformat(), data['type'],
                                 json.dumps(data, ensure_ascii=False), ip_hash,
                                 (self.headers.get('User-Agent') or '')[:200], idem, ph))
                            lead_id = cur.lastrowid
                            c.executemany('INSERT INTO outbox(lead_id, channel) VALUES(?, ?)',
                                          [(lead_id, ch) for ch in chans])
                            c.commit()
                            # Charge only after durability, before another
                            # request can check the same limit under _db_lock.
                            rate_commit(ip, 'lead', 'lead_day')
                finally:
                    c.close()
        except sqlite3.IntegrityError:
            # Shared SQLite file across app processes: preserve existing
            # database-enforced key uniqueness and replay behavior.
            replay = self.idem_replay(idem, ph) if idem else None
            if replay:
                return replay()
            log.error('lead storage integrity error ip_hash=%s', _ip_hash(ip))
            return self.send_json(500, {'ok': False, 'error': 'storage'})
        except Exception as e:  # noqa: BLE001
            log.error('lead storage failed ip_hash=%s err=%s', _ip_hash(ip), type(e).__name__)
            return self.send_json(500, {'ok': False, 'error': 'storage'})
        if existing is not None:
            if existing[1] != ph:
                log.warning('lead idempotency conflict id=%s', existing[0])
                return self.send_json(409, {'ok': False, 'error': 'idempotency_conflict'})
            return self.send_json(201, {'ok': True, 'ref': f'PBT-{existing[0]:06d}', 'replayed': True})
        if quota_raced:
            return self.rate_limited(ip)
        _wake.set()
        log.info('lead stored id=%s type=%s outbox=%s', lead_id, data['type'], ','.join(chans) or 'local')
        return self.send_json(201, {'ok': True, 'ref': f'PBT-{lead_id:06d}'})

    def rate_limited(self, ip):
        log.warning('lead rejected: rate ip_hash=%s', _ip_hash(ip))
        return self.send_json(429, {'ok': False, 'error': 'rate', 'message': 'Забагато запитів. Спробуй за 10 хвилин.'})

    def idem_replay(self, idem, ph):
        """Повтор того самого логічного запиту → та сама заявка (201, той самий ref, "replayed": true); той самий ключ з іншим
        змістом → 409. None — ключ ще не бачений."""
        try:
            with _db_lock:
                c = db()
                try:
                    row = c.execute('SELECT id, payload_hash FROM leads WHERE idem_key=?', (idem,)).fetchone()
                finally:
                    c.close()
        except Exception as e:  # noqa: BLE001 — OPS-2: помилка БД тут рвала з'єднання без відповіді й без запису в журнал
            log.error('lead storage failed (idempotency lookup) ip_hash=%s err=%s', _ip_hash(self.client_ip()), type(e).__name__)
            return lambda: self.send_json(500, {'ok': False, 'error': 'storage'})
        if not row:
            return None
        if row[1] != ph:
            log.warning('lead idempotency conflict id=%s', row[0])
            return lambda: self.send_json(409, {'ok': False, 'error': 'idempotency_conflict'})
        return lambda: self.send_json(201, {'ok': True, 'ref': f'PBT-{row[0]:06d}', 'replayed': True})


class Server(ThreadingHTTPServer):
    """SEC-1: не більше MAX_CONNECTIONS потоків-з'єднань (systemd TasksMax=256). Дозвіл береться до створення потоку і
    повертається у finally самого потоку; не отримали за CONN_SLOT_WAIT с — з'єднання закривається."""
    def __init__(self, addr, handler, max_conn=128, slot_wait=10.0):
        self._slots, self.max_conn, self.slot_wait = threading.BoundedSemaphore(max_conn), max_conn, slot_wait
        super().__init__(addr, handler)

    def process_request(self, request, client_address):
        if not self._slots.acquire(timeout=self.slot_wait):
            log.warning('connection dropped: all %s slots busy', self.max_conn)
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()             # потік не стартував — його finally не спрацює
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()


_single_process_guard = []


def acquire_single_process_guard():
    """Rate limits and the delivery worker live in one process's memory. A second server on the same
    database would silently double every quota, so the unsupported topology refuses to start.
    A kernel lock: SIGKILL releases it, leaving nothing to clean up. ops/restore.py takes it too."""
    fd = os.open(f'{DB}.server-lock', os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        raise SystemExit('single_process_guard: another process holds this lead database') from None
    _single_process_guard.append(fd)


def main():
    acquire_single_process_guard()
    host, port = ENV('HOST') or '127.0.0.1', int(ENV('PORT') or 4180)
    max_conn = int(ENV('MAX_CONNECTIONS') or 128)
    if not 1 <= max_conn <= 200:
        raise SystemExit('MAX_CONNECTIONS must be 1..200 (systemd TasksMax=256)')
    slot_wait = float(ENV('CONN_SLOT_WAIT') or Handler.header_timeout)
    if not math.isfinite(slot_wait) or not 0 <= slot_wait <= 120:
        raise SystemExit('CONN_SLOT_WAIT must be finite and between 0 and 120')
    srv = Server((host, port), Handler, max_conn, slot_wait)
    if not _schema_ok.is_set():
        threading.Thread(target=migrate_retry_worker, name='migrate', daemon=True).start()
    if (ENV('DELIVERY_WORKER') or '1') != '0':      # 0 — лише для тестів («падіння до доставки»)
        threading.Thread(target=delivery_worker, name='delivery', daemon=True).start()
    print(f'ПБТ · ПолтаваБудТехніка → http://{host}:{port}/')
    srv.serve_forever()


if __name__ == '__main__':
    main()
