"""Issue #4: доступне перемикання тем, збереження і відсутність FOUC."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_restore_precedes_stylesheets_and_csp_stays_hash_based(server):
    for file in ("index.html", "404.html"):
        html = (ROOT / "web" / file).read_text(encoding="utf-8")
        assert "localStorage.getItem('pbt-theme')" in html
        assert html.index("dataset.theme") < html.index('rel="stylesheet"')
        assert "css/precision.css" not in html
    import urllib.request
    with urllib.request.urlopen(server["base"] + "/") as response:
        csp = response.headers["Content-Security-Policy"]
    assert "script-src 'self' " in csp and "'sha256-" in csp
    assert "script-src 'self' 'unsafe-inline'" not in csp
    assert "unsafe-eval" not in csp


@pytest.mark.parametrize("width,height,mobile", [
    (1440, 900, False),
    (1024, 768, False),
    (820, 1180, True),
    (390, 844, True),
    (360, 640, True),
    (320, 568, True),
])
def test_theme_toggle_keyboard_storage_and_back_forward(page_factory, width, height, mobile):
    page = page_factory(width, height, mobile=mobile, reduced=True)
    sky = page.locator('[data-theme-choice="sky"]')
    precision = page.locator('[data-theme-choice="precision"]')
    assert page.evaluate("document.documentElement.dataset.theme") == "sky"
    assert sky.get_attribute("aria-pressed") == "true"
    assert precision.get_attribute("aria-pressed") == "false"

    precision.focus()
    page.keyboard.press("Enter")
    assert page.evaluate("document.documentElement.dataset.theme") == "precision"
    assert precision.get_attribute("aria-pressed") == "true"
    assert sky.get_attribute("aria-pressed") == "false"
    assert page.evaluate("localStorage.getItem('pbt-theme')") == "precision"
    assert page.evaluate("document.querySelector('meta[name=theme-color]').content") == "#101820"
    page.reload(wait_until="networkidle")
    assert page.evaluate("document.documentElement.dataset.theme") == "precision"
    assert page.locator('[data-theme-choice="precision"]').get_attribute("aria-pressed") == "true"

    sky.focus()
    page.keyboard.press("Space")
    assert page.evaluate("document.documentElement.dataset.theme") == "sky"
    assert sky.get_attribute("aria-pressed") == "true"
    assert page.evaluate("localStorage.getItem('pbt-theme')") == "sky"
    assert page.evaluate("document.querySelector('meta[name=theme-color]').content") == "#05080D"


def test_no_cross_theme_media_fetches_or_dom_rebuild(page_factory):
    page = page_factory(reduced=True)
    before = page.evaluate("""() => ({
      images: [...document.querySelectorAll('img')].map(x => x.getAttribute('src')),
      videos: [...document.querySelectorAll('video')].map(x => x.getAttribute('src')),
      fleet: [...document.querySelectorAll('#park .unit')].map(x => x.dataset.id)
    })""")
    page.locator('[data-theme-choice="precision"]').click()
    page.locator('[data-theme-choice="sky"]').click()
    after = page.evaluate("""() => ({
      images: [...document.querySelectorAll('img')].map(x => x.getAttribute('src')),
      videos: [...document.querySelectorAll('video')].map(x => x.getAttribute('src')),
      fleet: [...document.querySelectorAll('#park .unit')].map(x => x.dataset.id)
    })""")
    assert before == after


def test_storage_denied_still_allows_in_memory_theme_selection(browser, server):
    context = browser.new_context()
    try:
        context.add_init_script("""Object.defineProperty(window, 'localStorage', {
          configurable: true, get() { throw new Error('Storage disabled') }
        });""")
        page = context.new_page()
        page.goto(server["base"] + "/", wait_until="networkidle")
        assert page.evaluate("document.documentElement.dataset.theme") == "sky"
        page.locator('[data-theme-choice="precision"]').click()
        assert page.evaluate("document.documentElement.dataset.theme") == "precision"
        assert page.locator("#park .unit").count() == 32
    finally:
        context.close()


@pytest.mark.parametrize("theme", ["sky", "precision"])
@pytest.mark.parametrize("width,height,mobile", [
    (1440, 900, False),
    (1024, 768, False),
    (820, 1180, True),
    (390, 844, True),
    (360, 640, True),
    (320, 568, True),
], ids=["desktop", "small-desktop", "tablet", "phone", "small-phone", "minimum-phone"])
def test_axe_wcag22aa_zero_violations_in_each_theme(page_factory, theme, width, height, mobile):
    page = page_factory(width, height, mobile=mobile, reduced=True, bypass_csp=True)
    page.locator(f'[data-theme-choice="{theme}"]').click()
    page.add_script_tag(path=str(ROOT / "tests" / "vendor" / "axe.min.js"))
    page.add_style_tag(content="*,*::before,*::after{transition:none!important;animation:none!important}")
    page.evaluate("document.querySelectorAll('.rv').forEach(el => el.classList.add('is-in'))")
    result = page.evaluate("""async () => axe.run(document, {
      runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']}
    })""")
    bad = [(v["id"], v.get("impact"), [n["target"] for n in v["nodes"]][:3]) for v in result["violations"]]
    assert not bad, bad


@pytest.mark.parametrize("width,height,mobile", [
    (1440, 900, False),
    (1024, 768, False),
    (820, 1180, True),
    (390, 844, True),
    (360, 640, True),
    (320, 568, True),
], ids=["desktop", "small-desktop", "tablet", "phone", "small-phone", "minimum-phone"])
def test_theme_switch_has_no_delayed_unprompted_cls(page_factory, width, height, mobile):
    page = page_factory(width, height, mobile=mobile, reduced=True)
    page.evaluate("""() => {
      window.__unexpectedShifts = [];
      new PerformanceObserver(list => {
        for (const entry of list.getEntries())
          if (!entry.hadRecentInput) window.__unexpectedShifts.push(entry.value);
      }).observe({type: 'layout-shift'});
    }""")
    page.locator('[data-theme-choice="precision"]').click()
    page.wait_for_timeout(700)
    page.locator('[data-theme-choice="sky"]').click()
    page.wait_for_timeout(700)
    assert page.evaluate("window.__unexpectedShifts.reduce((a,b)=>a+b,0)") <= 0.001


def test_csp_no_inline_script_weakening_in_backend_source():
    server = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
    assert "_inline_script_hashes()" in server
    assert "script-src 'self'" in server
    assert "script-src 'self' 'unsafe-inline'" not in server


@pytest.mark.parametrize("theme", ["sky", "precision"])
@pytest.mark.parametrize("path", ["/", "/missing-page"])
def test_prepaint_restores_storage_under_enforced_browser_csp(browser, server, theme, path):
    """Real browser must execute the allowlisted prepaint code while blocking unknown inline scripts."""
    import json
    context = browser.new_context()
    try:
        context.add_init_script("localStorage.setItem('pbt-theme', " + json.dumps(theme) + ");")
        page = context.new_page()
        response = page.goto(server["base"] + path, wait_until="load")
        assert response.status == (200 if path == "/" else 404)
        assert page.evaluate("document.documentElement.dataset.theme") == theme
        assert page.evaluate("document.querySelector('meta[name=theme-color]').content") == (
            "#101820" if theme == "precision" else "#05080D"
        )
        executed = page.evaluate("""() => {
          const el = document.createElement('script');
          // Два незалежні шари: Trusted Types забороняє сам рядок скрипта (TypeError), хеш-CSP — його виконання.
          try { el.textContent = 'window.__pbtUnexpectedInline = true'; } catch (e) { if (e.name === 'TypeError') return false; throw e; }
          document.head.appendChild(el);
          el.remove();
          return window.__pbtUnexpectedInline === true;
        }""")
        assert not executed, "unknown inline script bypassed Content-Security-Policy"
    finally:
        context.close()


def test_default_browser_chrome_color_agrees_with_sky_before_prepaint():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert '<html lang="uk" data-theme="sky">' in html
    assert '<meta name="theme-color" content="#05080D">' in html



@pytest.mark.parametrize("theme", ["sky", "precision"])
@pytest.mark.parametrize("state", ["modal-menu", "invalid-form"])
def test_axe_wcag22aa_checks_dynamic_interaction_states(page_factory, theme, state):
    """Rendered state changes are in-scope WCAG 2.2 AA, not only initial page."""
    page = page_factory(390, 844, mobile=True, reduced=True, bypass_csp=True)
    page.locator(f'[data-theme-choice="{theme}"]').click()
    if state == "modal-menu":
        page.locator(".burger").click()
        assert page.locator("#menu").is_visible()
    else:
        page.locator("#contact").fill("invalid")
        page.locator("#hours").fill("0")
        page.locator("#send").click()
        assert page.locator("#contact").get_attribute("aria-invalid") == "true"
    page.add_script_tag(path=str(ROOT / "tests" / "vendor" / "axe.min.js"))
    page.add_style_tag(content="*,*::before,*::after{transition:none!important;animation:none!important}")
    page.evaluate("document.querySelectorAll('.rv').forEach(el => el.classList.add('is-in'))")
    result = page.evaluate("""async () => axe.run(document, {
      runOnly: {type: 'tag', values:
        ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']}
    })""")
    bad = [(v["id"], v["impact"], [n["target"] for n in v["nodes"]][:3])
           for v in result["violations"]]
    assert not bad, bad



def test_accessible_names_include_actual_visible_control_labels(page_factory):
    """WCAG 2.1 SC 2.5.3: visible button/link text must occur in its accessible name."""
    pg = page_factory(reduced=True)
    for theme in ("sky", "precision"):
        control = pg.locator(f'[data-theme-choice="{theme}"]')
        assert control.inner_text().strip().casefold() in (
            control.get_attribute("aria-label") or ""
        ).casefold()
    brand = json.loads((ROOT / "config/business.json").read_text(encoding="utf-8"))["brand"]["nameUk"].casefold()
    assert brand
    for control in pg.locator("a.brand").all():
        assert brand in (control.get_attribute("aria-label") or "").casefold()
    assert "onsubmit=" not in (ROOT / "web" / "index.html").read_text(encoding="utf-8")


@pytest.mark.parametrize('engine', ['chromium', 'webkit'])
@pytest.mark.parametrize('initial,changed', [('sky', 'precision'), ('precision', 'sky')])
def test_other_tab_selection_does_not_shift_page_and_reload_restores_choice(pw, server, engine, initial, changed):
    """Тема вкладки стабільна; наступне завантаження читає спільне сховище."""
    browser = getattr(pw, engine).launch()
    context = browser.new_context(viewport={'width': 390, 'height': 844}, reduced_motion='reduce')
    first, second = context.new_page(), context.new_page()
    try:
        response = first.goto(server['base'] + '/', wait_until='networkidle')
        assert response.status == 200
        csp = response.headers['content-security-policy']
        assert "script-src 'self' " in csp and "'sha256-" in csp
        assert "script-src 'self' 'unsafe-inline'" not in csp
        first.locator(f'[data-theme-choice="{initial}"]').click()
        second.goto(server['base'] + '/', wait_until='networkidle')
        assert second.evaluate('document.documentElement.dataset.theme') == initial
        first.wait_for_timeout(700)  # HadRecentInput в першій вкладці має минути.
        first.evaluate("""() => {
          window.__storageSeen = false;
          window.__crossTabShifts = [];
          window.addEventListener('storage', e => {
            if (e.key === 'pbt-theme') window.__storageSeen = true;
          });
          window.__hasLayoutShift = PerformanceObserver.supportedEntryTypes.includes('layout-shift');
          if (window.__hasLayoutShift) new PerformanceObserver(list => {
            for (const e of list.getEntries()) if (!e.hadRecentInput) window.__crossTabShifts.push(e.value);
          }).observe({type: 'layout-shift'});
        }""")
        second.locator(f'[data-theme-choice="{changed}"]').click()
        first.wait_for_function('() => window.__storageSeen === true')
        first.wait_for_timeout(700)
        if engine == 'chromium':
            assert first.evaluate('window.__hasLayoutShift'), 'Chromium layout-shift observer unavailable'
        if first.evaluate('window.__hasLayoutShift'):
            shifts = first.evaluate('window.__crossTabShifts')
            assert not shifts, shifts
        assert first.evaluate('document.documentElement.dataset.theme') == initial
        assert first.locator(f'[data-theme-choice="{initial}"]').get_attribute('aria-pressed') == 'true'
        assert first.locator(f'[data-theme-choice="{changed}"]').get_attribute('aria-pressed') == 'false'
        assert first.evaluate("localStorage.getItem('pbt-theme')") == changed
        first.reload(wait_until='networkidle')
        assert first.evaluate('document.documentElement.dataset.theme') == changed
        assert first.locator(f'[data-theme-choice="{changed}"]').get_attribute('aria-pressed') == 'true'
        assert first.locator(f'[data-theme-choice="{initial}"]').get_attribute('aria-pressed') == 'false'
        executed = first.evaluate("""() => {
          const script = document.createElement('script');
          try { script.textContent = 'window.__unexpectedInline = true'; } catch (e) { if (e.name === 'TypeError') return false; throw e; }   // Trusted Types
          document.head.appendChild(script); script.remove();
          return window.__unexpectedInline === true;
        }""")
        assert not executed
    finally:
        context.close()
        browser.close()
