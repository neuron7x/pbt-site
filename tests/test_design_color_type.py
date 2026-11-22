"""Perceptible form text and readable type in both actual rendered themes."""
import re

import pytest


def contrast(a, b):
    def luminance(rgb):
        def lin(v):
            x = v / 255
            return x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4
        return sum(w * lin(v) for w, v in zip((.2126, .7152, .0722), rgb))
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + .05) / (dark + .05)


def rgb(value):
    values = re.findall(r'[\d.]+', value)
    assert len(values) >= 3, value
    if value.startswith('rgba'):
        assert len(values) == 4 and float(values[3]) == 1, value
    return tuple(map(int, values[:3]))


@pytest.mark.parametrize('theme', ['sky', 'precision'])
def test_placeholder_contrast_in_actual_form(page_factory, theme):
    page = page_factory(reduced=True)
    page.locator(f'[data-theme-choice="{theme}"]').click()
    sample = page.locator('#subject').evaluate("""el => ({
      foreground: getComputedStyle(el, '::placeholder').color,
      background: getComputedStyle(el).backgroundColor
    })""")
    assert contrast(rgb(sample['foreground']), rgb(sample['background'])) >= 4.5, sample
    page.locator('#subject').focus()
    focused = page.locator('#subject').evaluate("""el => ({
      foreground: getComputedStyle(el, '::placeholder').color,
      background: getComputedStyle(el).backgroundColor
    })""")
    assert contrast(rgb(focused['foreground']), rgb(focused['background'])) >= 4.5, focused


@pytest.mark.parametrize('theme', ['sky', 'precision'])
def test_confirmation_reference_contrast_in_actual_ui(page_factory, theme):
    page = page_factory(reduced=True)
    page.locator(f'[data-theme-choice="{theme}"]').click()
    page.route('**/api/lead', lambda route: route.fulfill(
        status=201, content_type='application/json', body='{"ok": true, "ref": "PBT-123456"}'))
    page.locator('#subject').fill('Екскаватор')
    page.locator('#contact').fill('0970000000')
    page.locator('#send').click()
    page.locator('#done.is-on').wait_for()
    assert ''.join(page.locator('#ref').inner_text().split()) == '№123456'
    sample = page.locator('#ref').evaluate("""el => ({
      foreground: getComputedStyle(el).color,
      fill: getComputedStyle(el).webkitTextFillColor,
      gradient: getComputedStyle(el).backgroundImage,
      background: getComputedStyle(el.closest('.done')).backgroundColor
    })""")
    assert sample['gradient'] == 'none', sample
    assert contrast(rgb(sample['foreground']), rgb(sample['background'])) >= 3, sample
    assert contrast(rgb(sample['fill']), rgb(sample['background'])) >= 3, sample


def test_contrast_checks_reject_the_original_palette():
    # Negative controls for the two actual defects seen before this change.
    assert contrast((127, 153, 187), (234, 247, 255)) < 4.5
    assert contrast((255, 215, 0), (255, 255, 255)) < 3
    with pytest.raises(AssertionError):
        rgb('rgba(0, 0, 0, 0)')


@pytest.mark.parametrize('theme', ['sky', 'precision'])
@pytest.mark.parametrize('width', [320, 360, 390])
def test_catalog_cards_remain_readable_and_actionable_on_small_screens(page_factory, theme, width):
    page = page_factory(w=width, h=800, mobile=True, reduced=True)
    page.locator(f'[data-theme-choice="{theme}"]').click()
    cards = page.locator('.unit')
    assert cards.count() == 32
    problems = cards.evaluate_all('''cards => cards.flatMap(card => {
      const rect = el => el.getBoundingClientRect();
      const c = rect(card), body = rect(card.querySelector('.unit__body'));
      const title = rect(card.querySelector('h3')), foot = rect(card.querySelector('.unit__foot'));
      const price = rect(card.querySelector('.unit__price')), button = rect(card.querySelector('button'));
      const eps = 1;
      const issues = [];
      if (c.left < -eps || c.right > innerWidth + eps) issues.push('card outside viewport');
      if (title.left < body.left - eps || title.right > body.right + eps) issues.push('title overflow');
      if (body.bottom > foot.top + eps) issues.push('body overlaps footer');
      if (price.right > button.left + eps && price.top < button.bottom && button.top < price.bottom) issues.push('price overlaps button');
      if (button.left < c.left - eps || button.right > c.right + eps || button.bottom > c.bottom + eps)
        issues.push('button outside card');
      const nodes = card.querySelectorAll('h3, dt, dd, .unit__price, .unit__price small, button');
      for (const n of nodes) if (n.scrollWidth > n.clientWidth + eps || n.scrollHeight > n.clientHeight + eps)
        issues.push('clipped: ' + n.className + ' ' + n.textContent.trim());
      return issues.map(issue => card.dataset.id + ': ' + issue);
    })''')
    assert not problems, problems


@pytest.mark.parametrize('theme', ['sky', 'precision'])
@pytest.mark.parametrize('width', [320, 390])
def test_user_text_spacing_override_preserves_content(page_factory, theme, width):
    page = page_factory(w=width, h=844, mobile=True, reduced=True, bypass_csp=True)
    page.locator(f'[data-theme-choice="{theme}"]').click()
    page.add_style_tag(content='* { line-height: 1.5 !important; letter-spacing: .12em !important; word-spacing: .16em !important; }')
    problems = page.evaluate('''() => {
      const errors = [];
      if (document.documentElement.scrollWidth > innerWidth + 1) errors.push('document horizontal overflow');
      const selectors = ['#heroTitle', '.hero__lead', '.hero .row', '.hero__stats',
        '.unit h3', '.unit__foot', '#subject', 'label[for="subject"]', '#send'];
      for (const selector of selectors) {
        const el = document.querySelector(selector);
        const r = el.getBoundingClientRect();
        if (r.left < -1 || r.right > innerWidth + 1) errors.push(selector + ' outside viewport');
        const style = getComputedStyle(el);
        if ((style.overflowX === 'hidden' || style.overflowX === 'clip') && el.scrollWidth > el.clientWidth + 1)
          errors.push(selector + ' horizontally clipped');
        if ((style.overflowY === 'hidden' || style.overflowY === 'clip') && el.scrollHeight > el.clientHeight + 1)
          errors.push(selector + ' vertically clipped');
      }
      const hero = document.querySelector('.hero').getBoundingClientRect();
      for (const selector of ['#heroTitle', '.hero__lead', '.hero .row', '.hero__stats']) {
        if (document.querySelector(selector).getBoundingClientRect().bottom > hero.bottom + 1)
          errors.push(selector + ' outside hero');
      }
      const stats = [...document.querySelectorAll('.hero__stats li')];
      for (let i = 0; i < stats.length - 1; i++) {
        const a = stats[i].querySelector('span').getBoundingClientRect();
        const b = stats[i + 1].querySelector('span').getBoundingClientRect();
        if (a.right > b.left + 1 && a.top < b.bottom && b.top < a.bottom)
          errors.push('hero statistic labels overlap');
      }
      for (const card of document.querySelectorAll('.unit')) {
        const title = card.querySelector('h3').getBoundingClientRect();
        const body = card.querySelector('.unit__body').getBoundingClientRect();
        const price = card.querySelector('.unit__price').getBoundingClientRect();
        const button = card.querySelector('button').getBoundingClientRect();
        if (title.right > body.right + 1) errors.push('card ' + card.dataset.id + ' title outside body');
        if (price.right > button.left + 1 && price.top < button.bottom && button.top < price.bottom)
          errors.push('card ' + card.dataset.id + ' price overlaps button');
      }
      return errors;
    }''')
    assert not problems, problems


@pytest.mark.parametrize('theme', ['sky', 'precision'])
@pytest.mark.parametrize('width,height', [(320, 568), (568, 320)])
@pytest.mark.parametrize('spacing', [False, True])
def test_text_spacing_in_moving_hero_preserves_access(page_factory, theme, width, height, spacing):
    page = page_factory(w=width, h=height, mobile=True, reduced=False, bypass_csp=True)
    page.locator(f'[data-theme-choice="{theme}"]').click()
    if spacing:
        page.add_style_tag(content='* { line-height: 1.5 !important; letter-spacing: .12em !important; word-spacing: .16em !important; } p { margin-bottom: 2em !important; }')
    page.wait_for_timeout(1300)
    problem = page.evaluate('''() => {
      const box = s => document.querySelector(s).getBoundingClientRect();
      const nav = box('#nav'), eyebrow = box('#heroCenter .eyebrow'), stats = box('.hero__stats');
      const toggle = box('#motionToggle'), hero = box('#hero');
      const intersects = (a,b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
      const problems = [];
      if (intersects(nav, eyebrow)) problems.push('navigation overlaps eyebrow');
      for (const selector of ['#heroCenter .eyebrow', '#heroTitle', '#heroCenter .btn', '.hero__stats'])
        if (intersects(toggle, box(selector))) problems.push('motion control overlaps ' + selector);
      if (eyebrow.top < hero.top || stats.bottom > hero.bottom + 1) problems.push('hero content clipped');
      return problems;
    }''')
    assert not problem, problem
    page.locator('.hero__stats').scroll_into_view_if_needed()
    assert page.locator('.hero__stats').evaluate('el => { const r = el.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; }')


@pytest.mark.parametrize('theme', ['sky', 'precision'])
@pytest.mark.parametrize('width,height', [(568, 320), (667, 375)])
@pytest.mark.parametrize('spacing', [False, True])
def test_landscape_motion_control_text_fits_without_covering_hero(page_factory, theme, width, height, spacing):
    page = page_factory(w=width, h=height, mobile=True, reduced=False, bypass_csp=True)
    page.locator(f'[data-theme-choice="{theme}"]').click()
    if spacing:
        page.add_style_tag(content='* { line-height: 1.5 !important; letter-spacing: .12em !important; word-spacing: .16em !important; } p { margin-bottom: 2em !important; }')
    page.wait_for_timeout(1300)
    problems = page.locator('#motionToggle').evaluate('''button => {
      const problems = [], rect = button.getBoundingClientRect();
      const range = document.createRange(); range.selectNodeContents(button);
      for (const line of range.getClientRects()) {
        if (line.left < rect.left - .1 || line.right > rect.right + .1 ||
            line.top < rect.top - .1 || line.bottom > rect.bottom + .1)
          problems.push('motion control text extends outside button');
      }
      const stats = document.querySelector('.hero__stats').getBoundingClientRect();
      if (rect.left < stats.right && stats.left < rect.right && rect.top < stats.bottom && stats.top < rect.bottom)
        problems.push('motion control covers statistics');
      return problems;
    }''')
    assert not problems, problems
