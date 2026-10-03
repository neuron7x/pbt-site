"""Фікстури: ізольований сервер (власна БД, високі ліміти) + браузер Playwright."""
import os, socket, subprocess, sys, time, urllib.request
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def _free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p


@pytest.fixture(scope='session')
def server(tmp_path_factory):
    port = _free_port()
    db = tmp_path_factory.mktemp('db') / 'leads.db'
    env = {**os.environ, 'PORT': str(port), 'HOST': '127.0.0.1', 'LEAD_DB': str(db),
           'RATE_ANY_10MIN': '10000', 'RATE_LEAD_10MIN': '10000', 'RATE_LEAD_DAY': '10000',
           'TELEGRAM_BOT_TOKEN': '', 'LEAD_WEBHOOK_URL': '', 'TRUST_PROXY': '1'}   # як у розгортанні (ops/systemd)
    proc = subprocess.Popen([sys.executable, str(ROOT / 'server' / 'app.py')], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f'http://127.0.0.1:{port}'
    for _ in range(50):
        try:
            urllib.request.urlopen(base + '/api/health', timeout=.5); break
        except Exception:
            time.sleep(.1)
    yield {'base': base, 'db': db}
    proc.terminate(); proc.wait(5)


@pytest.fixture(scope='session')
def pw():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope='session')
def browser(pw):
    b = pw.chromium.launch()
    yield b
    b.close()


@pytest.fixture
def page_factory(browser, server):
    ctxs = []

    def make(w=1440, h=900, mobile=False, reduced=False, path='/', bypass_csp=False):
        c = browser.new_context(viewport={'width': w, 'height': h}, is_mobile=mobile, has_touch=mobile, bypass_csp=bypass_csp,
                                device_scale_factor=2 if mobile else 1, reduced_motion='reduce' if reduced else 'no-preference')
        ctxs.append(c)
        pg = c.new_page()
        pg.errors = []
        pg.on('pageerror', lambda e: pg.errors.append(f'pageerror: {e}'))
        pg.on('console', lambda m: pg.errors.append(f'console: {m.text}') if m.type == 'error' else None)
        pg.on('response', lambda r: pg.errors.append(f'{r.status} {r.url}') if r.status >= 400 and '/api/lead' not in r.url else None)
        pg.on('requestfailed', lambda r: pg.errors.append(f'failed {r.url}') if 'media/hero' not in r.url else None)
        pg.goto(server['base'] + path, wait_until='networkidle')
        pg.wait_for_timeout(600)
        return pg
    yield make
    for c in ctxs:
        c.close()
