"""W3C Trusted Types і ізоляція походження.

CSP `require-trusted-types-for 'script'; trusted-types pbt` робить кожен рядковий синк HTML/скриптів помилкою в браузері,
а не питанням дисципліни: сайт будує DOM вузлами (el/append), а єдиний URL скрипта йде через політику `pbt`.
COOP/CORP same-origin відрізають чужі вікна й чужі вбудовування (клас Spectre / XS-Leaks).
"""
import urllib.request

import pytest


def _headers(base, path):
    with urllib.request.urlopen(base + path, timeout=10) as r:
        return r.headers


@pytest.mark.parametrize('path', ['/', '/css/site.css', '/js/site.js', '/nema-takoi-storinky'])
def test_isolation_and_trusted_types_headers_everywhere(server, path):
    try:
        h = _headers(server['base'], path)
    except urllib.error.HTTPError as e:                                   # 404 теж мусить нести заголовки
        h = e.headers
    csp = h['Content-Security-Policy']
    assert "require-trusted-types-for 'script'" in csp and 'trusted-types pbt' in csp, csp
    assert "object-src 'none'" in csp, csp
    assert h['Cross-Origin-Opener-Policy'] == 'same-origin'
    assert h['Cross-Origin-Resource-Policy'] == 'same-origin'


def test_string_html_sinks_are_blocked_by_the_browser(page_factory):
    pg = page_factory(1440, 900)
    res = pg.evaluate("""() => {
      const out = {};
      try { document.createElement('div').innerHTML = '<img src=x>'; out.inner = 'allowed'; } catch (e) { out.inner = e.name; }
      try { const s = document.createElement('script'); s.src = 'js/evil.js'; out.src = 'allowed'; } catch (e) { out.src = e.name; }
      try { document.createElement('div').insertAdjacentHTML('beforeend', '<b>x</b>'); out.adj = 'allowed'; } catch (e) { out.adj = e.name; }
      try { trustedTypes.createPolicy('rogue', {}); out.policy = 'allowed'; } catch (e) { out.policy = e.name; }
      return out; }""")
    assert res == {'inner': 'TypeError', 'src': 'TypeError', 'adj': 'TypeError', 'policy': 'TypeError'}, res
    assert not [e for e in pg.errors if 'Trusted Type' in e], pg.errors       # сам сайт жодного разу не порушив політику


def test_the_one_policy_admits_only_the_drawing_module(page_factory):
    pg = page_factory(1440, 900)
    pg.locator('.unit[data-id="ak-2"] .unit__pass').click()
    pg.locator('#passport[open]').wait_for()                             # модуль креслень завантажився через політику pbt
    assert pg.evaluate("typeof window.PBTBlueprint") == 'object'
    assert not [e for e in pg.errors if 'Trusted Type' in e or 'Content Security Policy' in e], pg.errors


@pytest.mark.parametrize('engine', ['webkit', 'firefox'])
def test_page_and_passport_work_in_other_engines(pw, server, engine):
    """Trusted Types примусово діють лише там, де браузер їх підтримує; деінде політика null і рядок той самий.
    Без skip: рушій, що не запустився, — червоне (у CI встановлено chromium, webkit, firefox)."""
    b = getattr(pw, engine).launch()
    try:
        pg = b.new_page(viewport={'width': 1440, 'height': 900})
        errors = []
        pg.on('pageerror', lambda e: errors.append(str(e)))
        pg.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        pg.goto(server['base'] + '/', wait_until='networkidle')
        pg.locator('#park .unit').nth(31).wait_for(state='attached')
        assert pg.locator('#park .unit').count() == 32
        btn = pg.locator('.unit[data-id="ak-2"] .unit__pass')
        btn.scroll_into_view_if_needed()
        pg.wait_for_timeout(900)                                          # картка проявляється (rv--scale): клікаємо стабільну ціль
        btn.click()
        pg.locator('#passport[open]').wait_for(timeout=10000)
        assert pg.locator('#passDraw svg.bp').count() == 1
        bad = [e for e in errors if 'Trusted' in e or 'Content Security Policy' in e or 'TypeError' in e]
        assert not bad, (engine, bad)
    finally:
        b.close()
