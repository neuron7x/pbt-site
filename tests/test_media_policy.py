"""Політика економії трафіку й пріоритетів завантаження шрифтів."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_preload_matches_selected_theme_only():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    faces = (ROOT / "web" / "css" / "fonts.css").read_text(encoding="utf-8")
    assert html.count('href="fonts/IBMPlexSans-400-cyrillic.woff2"') == 1
    assert 'id="themeFontPreload"' in html
    assert "theme==='precision'?'IBMPlexSans-600-cyrillic.woff2':'Tektur-var-cyrillic.woff2'" in html
    for variant in ("IBMPlexSans-600-cyrillic.woff2", "IBMPlexSans-400-cyrillic.woff2",
                    "Tektur-var-cyrillic.woff2"):
        assert variant in faces
        assert (ROOT / "web" / "fonts" / variant).is_file()


def test_save_data_does_not_fetch_autoplay_videos(browser, server):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    try:
        pg = ctx.new_page()
        pg.add_init_script("""Object.defineProperty(navigator, 'connection', {
          configurable: true, value: {saveData: true, effectiveType: '4g'}
        })""")
        pg.goto(server["base"] + "/", wait_until="networkidle")
        pg.wait_for_timeout(1250)
        assert pg.evaluate("document.documentElement.dataset.quality") == "reduced"
        assert pg.evaluate("document.getElementById('heroVideo').currentSrc") == ""
        assert pg.evaluate("document.getElementById('logoAnim').currentSrc") == ""
        assert pg.evaluate("!document.querySelector('#masshtab').classList.contains('is-pinned')")
        assert pg.locator("#cine figure img").count() == 6
        pg.evaluate("document.getElementById('jobs').scrollIntoView({behavior: 'instant'})")
        pg.wait_for_timeout(700)
        assert pg.evaluate("[...document.querySelectorAll('#jobs video')].every(v => !v.currentSrc)")
        pg.evaluate("document.getElementById('reel').scrollIntoView({behavior: 'instant'})")
        pg.wait_for_timeout(700)
        assert pg.evaluate("[...document.querySelectorAll('#reel video')].every(v => !v.currentSrc)")
        assert pg.locator("#park .unit").count() == 32
    finally:
        ctx.close()


def test_two_logical_cores_do_not_override_user_motion_preference(browser, server):
    """Наявність двох CPU у CI не дорівнює явному Save-Data."""
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    try:
        page = ctx.new_page()
        page.add_init_script("""Object.defineProperty(navigator, 'hardwareConcurrency', {
          configurable: true, value: 2
        });""")
        page.goto(server["base"] + "/", wait_until="networkidle")
        assert page.evaluate("document.documentElement.dataset.quality") == "reduced"
        page.wait_for_function("""() => {
          const v = document.getElementById('heroVideo');
          return !!v.currentSrc && v.readyState >= 1;
        }""", timeout=15000)
        assert page.evaluate("document.getElementById('heroVideo').currentSrc.includes('hero-wide')")
    finally:
        ctx.close()
