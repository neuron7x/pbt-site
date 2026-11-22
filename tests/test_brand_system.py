"""Інваріанти фірмової системи «Табличка машини» (docs/DESIGN.md): одна тема, без декоративного шуму."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / 'web/css/site.css').read_text(encoding='utf-8')
HTML = (ROOT / 'web/index.html').read_text(encoding='utf-8')
JS = (ROOT / 'web/js/site.js').read_text(encoding='utf-8')
GOLD = 'rgb(253, 197, 1)'


def test_single_theme_without_switch():
    for source in (CSS, HTML, JS, (ROOT / 'web/404.html').read_text(encoding='utf-8')):
        assert 'data-theme' not in source and 'pbt-theme' not in source and 'precision' not in source


def test_no_gradient_text_and_one_keyframe_for_confirmation_only():
    assert 'background-clip:text' not in CSS
    assert re.findall(r'@keyframes\s+([\w-]+)', CSS) == ['draw']


def test_decorative_layers_are_gone():
    for marker in ('id="glow"', 'id="gauge"', 'id="spark"', 'hero__beams', 'hero__water', 'class="wave"',
                   'class="marquee"', 'id="partners"', 'class="facts', 'job__n', 'data-count'):
        assert marker not in HTML, marker
    for marker in ('sparkLoop', 'countUp', 'gaugeRender', 'D.partners', 'cine__n', '--rx'):
        assert marker not in JS, marker


def test_section_heads_have_no_eyebrow_and_numbering_only_in_request_steps():
    heads = re.findall(r'<div class="sec-head">(.*?)</div>', HTML, re.S)
    assert len(heads) >= 7
    assert all('eyebrow' not in head for head in heads)
    numbered = re.findall(r'<span class="num">\d\d</span>', HTML)
    assert len(numbered) == 3 and HTML.index('request-steps') < HTML.index(numbered[0])


@pytest.mark.parametrize('width,height,mobile', [(1440, 900, False), (390, 844, True)])
def test_rendered_page_keeps_one_voice(page_factory, width, height, mobile):
    page = page_factory(width, height, mobile=mobile, reduced=True)
    facts = page.evaluate("""(gold) => {
      const heads = [...document.querySelectorAll('main h2')];
      const twoTone = heads.filter(h => [...h.querySelectorAll('span')].some(s => getComputedStyle(s).color !== getComputedStyle(h).color)).length;
      const centred = [...document.querySelectorAll('.sec-head')].filter(h => getComputedStyle(h).textAlign === 'center').length;
      const goldCards = [...document.querySelectorAll('.unit, .tile, .job')].filter(c =>
        [...c.querySelectorAll('*')].some(e => getComputedStyle(e).backgroundColor === gold)).length;
      return {heads: heads.length, twoTone, centred, goldCards, cards: document.querySelectorAll('.unit').length,
              overflow: document.documentElement.scrollWidth - innerWidth};
    }""", GOLD)
    assert facts['heads'] >= 8
    assert facts['twoTone'] == 0
    assert facts['centred'] == 0
    assert facts['cards'] == 32 and facts['goldCards'] == 0
    assert facts['overflow'] <= 0
