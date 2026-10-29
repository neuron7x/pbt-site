"""Issue #4: доступне перемикання тем, збереження і відсутність FOUC."""
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
      runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag22aa']}
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
def test_theme_switch_never_introduces_unsolicited_layout_shift(page_factory, width, height, mobile):
    page = page_factory(width, height, mobile=mobile, reduced=True)
    page.evaluate("""() => {
      window.__unexpectedShifts = [];
      new PerformanceObserver(list => {
        for (const entry of list.getEntries())
          if (!entry.hadRecentInput) window.__unexpectedShifts.push(entry.value);
      }).observe({type: 'layout-shift'});
    }""")
    page.locator('[data-theme-choice="precision"]').click()
    page.wait_for_timeout(180)
    page.locator('[data-theme-choice="sky"]').click()
    page.wait_for_timeout(180)
    assert page.evaluate("window.__unexpectedShifts.reduce((a,b)=>a+b,0)") <= 0.001


def test_csp_no_inline_script_weakening_in_backend_source():
    server = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
    assert "_inline_script_hashes()" in server
    assert "script-src 'self'" in server
    assert "script-src 'self' 'unsafe-inline'" not in server
