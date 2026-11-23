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

@pytest.mark.parametrize('theme', ['sky', 'precision'])
@pytest.mark.parametrize('width,height,mobile', [
    (1440, 900, False), (390, 844, True), (320, 568, True), (844, 390, True),
    (568, 320, True), (667, 375, True),
])
def test_hero_logo_is_compact_and_offer_is_clear(page_factory, theme, width, height, mobile):
    """Бренд лишається в шапці, а компактний знак не перетягує увагу з оферу."""
    page = page_factory(width, height, mobile=mobile, reduced=True)
    page.locator(f'[data-theme-choice="{theme}"]').click()
    page.wait_for_function("""() => {
      const width = document.querySelector('.logo-hero').getBoundingClientRect().width;
      return width >= 70 && width <= 104;
    }""", timeout=1500)
    logo = page.locator('.logo-hero').bounding_box()
    assert logo and 70 <= logo['width'] <= 104 and logo['width'] <= width * .28
    assert page.locator('#nav .brand__logo').is_visible()
    heading = page.locator('#heroTitle').inner_text().casefold()
    eyebrow_text = page.locator('#heroCenter .eyebrow').inner_text().casefold()
    # Service intent sits immediately above the original brand headline.
    assert 'оренда спецтехніки' in eyebrow_text and 'полтава' in eyebrow_text
    assert 'важкі умови' in heading and 'техніка під об’єкт' in heading and len(heading.split()) <= 6
    lead = page.locator('.hero__lead').text_content().casefold()
    assert all(term in lead for term in ('амфібії', 'крани', 'трали')) and len(lead.split()) <= 18
    assert page.locator('.hero__lead').is_visible() is (height > 520)
    assert '24/7' not in page.locator('#heroCenter .eyebrow').inner_text()
    assert page.locator('#heroCenter .btn').count() == 2
    for button in page.locator('#heroCenter .btn').all():
        box = button.bounding_box()
        assert box and box['height'] >= 44 and box['x'] >= 0 and box['x'] + box['width'] <= width
        assert box['y'] >= 0 and box['y'] + box['height'] <= height - 6
    stats = page.locator('.hero__stats li').evaluate_all(
        'els => els.map(el => Math.round(el.getBoundingClientRect().top))')
    assert len(stats) == 4 and len(set(stats)) == 1, stats
    assert page.locator('.hero__stats span').evaluate_all(
        'els => els.every(el => parseFloat(getComputedStyle(el).fontSize) >= 10)')
    nav = page.locator('#nav').bounding_box()
    eyebrow = page.locator('#heroCenter .eyebrow').bounding_box()
    numbers = page.locator('.hero__stats').bounding_box()
    assert nav and eyebrow and numbers
    assert eyebrow['y'] >= nav['y'] + nav['height'] + 6
    assert numbers['y'] + numbers['height'] <= height - 6


@pytest.mark.parametrize('engine', ['chromium', 'webkit'])
@pytest.mark.parametrize('theme', ['sky', 'precision'])
@pytest.mark.parametrize('width,height', [(568, 320), (667, 375)])
@pytest.mark.parametrize('reduced', [False, True])
def test_short_landscape_hero_is_visible_in_both_engines(pw, server, engine, theme, width, height, reduced):
    """Короткий landscape не обрізає зміст або доступні кнопки в жодному режимі руху."""
    browser = getattr(pw, engine).launch()
    context = browser.new_context(viewport={'width': width, 'height': height},
                                  is_mobile=True, has_touch=True,
                                  reduced_motion='reduce' if reduced else 'no-preference')
    context.add_init_script("Object.defineProperty(navigator, 'hardwareConcurrency', {configurable: true, value: 8})")
    page = context.new_page()
    try:
        page.goto(server['base'] + '/', wait_until='networkidle', timeout=45000)
        page.locator(f'[data-theme-choice="{theme}"]').click()
        page.wait_for_timeout(1300)  # завершити вхідну анімацію першого екрану
        hero = page.locator('#hero').bounding_box()
        nav = page.locator('#nav').bounding_box()
        assert hero and nav
        elements = page.locator('#heroCenter .eyebrow,#heroTitle,#heroCenter .btn,.hero__stats').all()
        assert len(elements) == 5
        for element in elements:
            box = element.bounding_box()
            assert box and box['x'] >= 0 and box['x'] + box['width'] <= width
            assert box['y'] >= nav['y'] + nav['height'] and box['y'] + box['height'] <= min(height, hero['y'] + hero['height']) - 6, box
        for button in page.locator('#heroCenter .btn').all():
            assert button.bounding_box()['height'] >= 44
        labels = page.locator('.hero__stats span')
        assert labels.count() == 4 and labels.evaluate_all(
            'els => els.every(el => parseFloat(getComputedStyle(el).fontSize) >= 10)')
        rows = page.locator('.hero__stats li').evaluate_all(
            'els => els.map(el => Math.round(el.getBoundingClientRect().top))')
        assert len(set(rows)) == 1, rows
    finally:
        context.close()
        browser.close()
