"""Власний логотип ПЛЕЙНБУД: цілісність ресурсів, одна назва в шапці, контраст на світлій шапці."""
import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
LOGO = ROOT / 'web/media/logo'
MANIFEST = json.loads((LOGO / 'plainbud-brand-manifest.json').read_text(encoding='utf-8'))


def test_manifest_matches_every_generated_file_and_generator():
    assert MANIFEST['schema'] == 'plainbud-brand-assets-v2'
    assert MANIFEST['font']['path'] == 'web/fonts/Tektur-var-cyrillic.woff2'
    assert MANIFEST['generator_sha256'] == hashlib.sha256((ROOT / 'tools/logo.py').read_bytes()).hexdigest()
    for name, item in MANIFEST['outputs'].items():
        data = (LOGO / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == item['sha256'], name
        assert len(data) == item['bytes'], name
    for name in ('plainbud-wordmark.svg', 'plainbud-lockup.svg', 'plainbud-mark.svg', 'plainbud-logo-nav-ink.webp'):
        assert name in MANIFEST['outputs'], name


def test_icons_are_opaque_ink_tiles_without_black_corners():
    ink = (6, 43, 92)
    for name in ('favicon.png', 'apple-touch-icon.png', 'icon-512.png'):
        with Image.open(LOGO / name) as image:
            rgb = image.convert('RGB')
            for corner in ((0, 0), (rgb.width - 1, 0), (0, rgb.height - 1), (rgb.width - 1, rgb.height - 1)):
                assert sum(abs(a - b) for a, b in zip(rgb.getpixel(corner), ink)) <= 12, (name, corner)


def test_nav_lockups_share_geometry_and_differ_only_in_wordmark_colour():
    with Image.open(LOGO / 'plainbud-logo-nav.webp') as gold, Image.open(LOGO / 'plainbud-logo-nav-ink.webp') as ink:
        assert gold.size == ink.size and gold.size[1] == 62
        alpha_gold, alpha_ink = gold.getchannel('A'), ink.getchannel('A')
        assert alpha_gold.tobytes() == alpha_ink.tobytes()


def test_header_carries_the_name_once():
    html = (ROOT / 'web/index.html').read_text(encoding='utf-8')
    header = html[html.index('<header class="nav" id="nav">'):html.index('</a>', html.index('<header class="nav"'))]
    assert 'data-brand' not in header and 'ПЛЕЙНБУД</b>' not in header
    assert 'plainbud-logo-nav.webp' in header and 'plainbud-logo-nav-ink.webp' in header


@pytest.mark.parametrize('theme', ['sky', 'precision'])
def test_solid_light_header_swaps_to_ink_lockup(page_factory, theme):
    page = page_factory(1440, 900, reduced=True)
    page.locator(f'[data-theme-choice="{theme}"]').click()
    assert page.locator('#nav .brand__logo').is_visible()
    assert not page.locator('#nav .brand__ink').is_visible()
    page.evaluate("document.getElementById('nav').classList.add('is-solid')")
    assert not page.locator('#nav .brand__logo').is_visible()
    assert page.locator('#nav .brand__ink').is_visible()
    assert page.evaluate("document.querySelector('#nav .brand__ink').naturalWidth") > 0
