"""Industrial Precision visual-contract tests.

These complement—not replace—the existing browser, accessibility, video and API
tests. Deliberately assert a small number of durable visual invariants instead
of hard-coding screenshots or animation timing.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_precision_css_is_loaded_after_base_on_all_public_pages():
    for filename in ("index.html", "404.html"):
        text = (ROOT / "web" / filename).read_text(encoding="utf-8")
        assert "css/precision.css" in text
        assert text.index("css/site.css") < text.index("css/precision.css")
        assert text.count("css/precision.css") == 1


def test_precision_layer_has_no_network_dependency():
    css = (ROOT / "web" / "css" / "precision.css").read_text(encoding="utf-8")
    assert "https://" not in css and "http://" not in css
    assert "@import" not in css
    assert "url(" not in css
    assert "--precision-graphite" in css and "--precision-paper" in css


@pytest.mark.parametrize("w,h,mobile", [
    (1440, 900, False),
    (820, 1180, True),
    (390, 844, True),
], ids=["desktop", "tablet", "phone"])
def test_precision_visual_contract_and_no_overflow(page_factory, w, h, mobile):
    pg = page_factory(w, h, mobile=mobile)
    values = pg.evaluate("""() => {
      const css = s => getComputedStyle(document.querySelector(s));
      return {
        body: css('body').backgroundColor,
        heading: css('h2').textTransform,
        font: css('h2').fontFamily,
        radius: css('.btn').borderTopLeftRadius,
        gauge: css('#gauge').display,
        glow: css('#glow').display,
        wave: css('.wave').display,
        hero: css('#hero').backgroundColor,
        overflow: document.scrollingElement.scrollWidth > innerWidth + 1,
        stylesheet: [...document.styleSheets].some(s =>
          s.href && s.href.includes('/css/precision.css'))
      };
    }""")
    assert values["body"] == "rgb(245, 245, 242)", values
    assert values["heading"] == "none", values
    assert "IBM Plex Sans" in values["font"], values
    assert values["radius"] == "5px", values
    assert values["gauge"] == values["glow"] == values["wave"] == "none", values
    assert values["hero"] == "rgb(16, 24, 32)", values
    assert values["stylesheet"] is True and values["overflow"] is False, values


def test_reduced_motion_remains_complete_and_not_video_dependent(page_factory):
    pg = page_factory(reduced=True)
    values = pg.evaluate("""() => ({
      quality: document.documentElement.dataset.quality,
      visibleTitle: !!document.querySelector('h1')?.getBoundingClientRect().height,
      fleet: document.querySelectorAll('#park .unit').length,
      video: document.getElementById('heroVideo').currentSrc,
      wave: getComputedStyle(document.querySelector('.wave')).display
    })""")
    assert values == {
        "quality": "static",
        "visibleTitle": True,
        "fleet": 32,
        "video": "",
        "wave": "none",
    }


def _luminance(color):
    rgb = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in rgb]
    return sum(a * b for a, b in zip(linear, (0.2126, 0.7152, 0.0722)))


@pytest.mark.parametrize("foreground,background", [
    ("#14202A", "#F5F5F2"),  # body copy on neutral paper
    ("#15202A", "#FDC501"),  # main CTA on brand gold
    ("#FFFFFF", "#14202A"),  # catalogue CTA on ink
    ("#FFFFFF", "#101820"),  # inverse heading on graphite
    ("#5B6974", "#F5F5F2"),  # subtle overline on paper
    ("#C6D2D9", "#101820"),  # inverse section-heading accent
    ("#1A5EA0", "#FFFFFF"),  # service link
])
def test_static_precision_pairs_meet_wcag_normal_text_contrast(foreground, background):
    """Static pairs only: moving video-frame contrast needs browser screenshots."""
    css = (ROOT / "web" / "css" / "precision.css").read_text(encoding="utf-8").upper()
    assert foreground in css and background in css
    a, b = _luminance(foreground), _luminance(background)
    ratio = (max(a, b) + 0.05) / (min(a, b) + 0.05)
    assert ratio >= 4.5, (foreground, background, ratio)
