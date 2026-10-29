"""Issue #4: обидві теми читають одну CSS token-систему без шару поверх шару."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "web" / "css" / "site.css"


def test_one_stylesheet_for_both_themes_and_offline_build():
    for name in ("index.html", "404.html"):
        html = (ROOT / "web" / name).read_text(encoding="utf-8")
        assert html.count("css/site.css") == 1
        assert "css/precision.css" not in html
    assert not (ROOT / "web" / "css" / "precision.css").exists()
    css = CSS.read_text(encoding="utf-8")
    assert ':root[data-theme="sky"]' in css
    assert ':root[data-theme="precision"]' in css
    assert "@import" not in css
    for token in ("--t-heading-case:", "--t-btn-bg:", "--t-nav-bg:",
                  "--t-hero-overlay:", "--t-unit-radius:", "--t-quote-bg:"):
        assert css.count(token) == 2, token


@pytest.mark.parametrize("width,height,mobile", [
    (1440, 900, False),
    (820, 1180, True),
    (390, 844, True),
], ids=["desktop", "tablet", "phone"])
def test_precision_token_contract_and_no_horizontal_overflow(page_factory, width, height, mobile):
    page = page_factory(width, height, mobile=mobile)
    assert page.evaluate("document.documentElement.dataset.theme") == "sky"
    page.locator('[data-theme-choice="precision"]').click()
    values = page.evaluate("""() => {
      const css = s => getComputedStyle(document.querySelector(s));
      return {
        body: css('body').backgroundColor,
        heading: css('h2').textTransform,
        font: css('h2').fontFamily,
        radius: css('.btn').borderTopLeftRadius,
        gauge: css('#gauge').display,
        wave: css('.wave').display,
        hero: css('#hero').backgroundColor,
        overflow: document.scrollingElement.scrollWidth > innerWidth + 1
      };
    }""")
    assert values["body"] == "rgb(245, 245, 242)", values
    assert values["heading"] == "none", values
    assert "IBM Plex Sans" in values["font"], values
    assert values["radius"] == "5px", values
    assert values["gauge"] == values["wave"] == "none", values
    assert values["hero"] == "rgb(16, 24, 32)", values
    assert not values["overflow"], values


def test_reduced_motion_is_complete_for_both_themes(page_factory):
    page = page_factory(reduced=True)
    for theme in ("sky", "precision"):
        page.locator(f'[data-theme-choice="{theme}"]').click()
        assert page.evaluate("document.documentElement.dataset.quality") == "static"
        assert page.locator("#park .unit").count() == 32
        assert page.locator("h1").is_visible()
        assert page.evaluate("!document.querySelector('#heroVideo').currentSrc")


def _luminance(color):
    rgb = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in rgb]
    return sum(a * b for a, b in zip(lin, (.2126, .7152, .0722)))


@pytest.mark.parametrize("foreground,background", [
    ("#14202A", "#F5F5F2"),
    ("#15202A", "#FDC501"),
    ("#FFFFFF", "#14202A"),
    ("#FFFFFF", "#101820"),
    ("#5B6974", "#F5F5F2"),
])
def test_static_palette_pairs_meet_wcag_aa(foreground, background):
    left, right = _luminance(foreground), _luminance(background)
    assert (max(left, right) + .05) / (min(left, right) + .05) >= 4.5


def test_not_found_surface_respects_persisted_theme(page_factory):
    page = page_factory()
    page.locator('[data-theme-choice="precision"]').click()
    page.goto(page.url.split("#")[0].rstrip("/") + "/nema-takoi-storinky")
    assert page.evaluate("document.documentElement.dataset.theme") == "precision"
    assert page.evaluate("getComputedStyle(document.querySelector('main')).backgroundColor") == "rgb(16, 24, 32)"
