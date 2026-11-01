"""WEB-01/04/05: keyboard journey, reflow, late font, and per-profile page transfer, in both themes.

These measure the page, not the repository's media inventory. Automated checks do not establish
WCAG conformance: screen-reader and real-device evaluation are separate and not done here.
"""
import json
from pathlib import Path
import sqlite3

from playwright.sync_api import expect
import pytest

ROOT = Path(__file__).resolve().parent.parent
BUDGET = json.loads((ROOT / 'config/network-budget.json').read_text(encoding='utf-8'))
THEMES = ('sky', 'precision')
MOBILE = dict(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
DESKTOP = dict(viewport={'width': 1440, 'height': 900})
FOCUS_STATE = """() => {
  const e = document.activeElement;
  if (!e || e === document.body) return null;
  const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  const top = document.elementFromPoint(cx, cy);
  return { id: e.id, tag: e.tagName, w: r.width, h: r.height, visible: s.visibility !== 'hidden' && s.display !== 'none',
           inView: r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth,
           covered: !!top && top !== e && !e.contains(top) && !top.contains(e) };
}"""


def _context(browser, theme, profile, **extra):
    ctx = browser.new_context(reduced_motion='reduce', **profile, **extra)
    ctx.add_init_script(f"try {{ localStorage.setItem('pbt-theme', '{theme}'); }} catch (_) {{}}")
    return ctx


@pytest.mark.parametrize('theme', THEMES)
@pytest.mark.parametrize('profile', [DESKTOP, MOBILE], ids=['desktop', 'mobile'])
def test_keyboard_alone_completes_the_lead_journey(browser, server, theme, profile):
    ctx = _context(browser, theme, profile)
    page = ctx.new_page()
    try:
        page.goto(server['base'], wait_until='networkidle')
        path = []
        for _ in range(300):
            page.keyboard.press('Tab')
            state = page.evaluate(FOCUS_STATE)
            assert state is not None, f'focus fell to body after {path[-3:]}'
            assert state['visible'] and state['w'] > 0 and state['h'] > 0, f'focused element invisible: {state}'
            assert state['inView'], f'focused element off screen: {state}'
            path.append(state['id'] or state['tag'])
            if state['id'] == 'subject':
                break
        else:
            pytest.fail(f'lead form not reachable by Tab; visited {len(path)}: {path[-5:]}')
        assert len(set(path)) > 3 or len(path) < 4, 'focus trap'
        subject = f'Клавіатурний шлях {theme} {profile["viewport"]["width"]}'
        page.keyboard.type(subject)
        page.locator('#contact').focus()
        page.keyboard.type('0971112233')
        page.locator('#send').focus()
        assert page.evaluate(FOCUS_STATE)['inView']
        page.keyboard.press('Enter')
        expect(page.locator('#done')).to_be_visible()
        assert page.evaluate("() => document.activeElement.id") == 'done'
        with sqlite3.connect(server['db']) as c:
            assert sum(json.loads(p)['subject'] == subject for (p,) in c.execute('SELECT payload FROM leads')) == 1
    finally:
        ctx.close()


@pytest.mark.parametrize('theme', THEMES)
def test_error_state_moves_focus_and_names_the_problem(browser, server, theme):
    ctx = _context(browser, theme, DESKTOP)
    page = ctx.new_page()
    try:
        page.goto(server['base'], wait_until='networkidle')
        page.locator('#send').focus()
        page.keyboard.press('Enter')
        state = page.evaluate("""() => { const e = document.activeElement, ids = (e.getAttribute('aria-describedby') || '').split(/\\s+/);
          return { id: e.id, invalid: e.getAttribute('aria-invalid'), text: ids.map(i => document.getElementById(i)?.textContent || '').join(' ').trim() }; }""")
        assert state['id'] == 'subject' and state['invalid'] == 'true' and len(state['text']) > 5
    finally:
        ctx.close()


@pytest.mark.parametrize('theme', THEMES)
def test_wcag_text_spacing_and_320px_reflow_do_not_clip_or_scroll_sideways(browser, server, theme):
    """WCAG 1.4.10 and 1.4.12 at the stated thresholds: this is the positive claim, nothing broader."""
    ctx = _context(browser, theme, dict(viewport={'width': 320, 'height': 640}))
    page = ctx.new_page()
    try:
        page.goto(server['base'], wait_until='networkidle')
        page.add_style_tag(content="* { line-height: 1.5 !important; letter-spacing: .12em !important; word-spacing: .16em !important; } p { margin-bottom: 2em !important; }")
        page.wait_for_timeout(300)
        result = page.evaluate("""() => {
          const clipped = [...document.querySelectorAll('#zapyt label, #zapyt button, #zapyt input, #zapyt select')].filter(e => e.id !== 'website' && !e.querySelector('#website') && e.getAttribute('for') !== 'website').filter(e => {
            const r = e.getBoundingClientRect(); return r.width > 0 && (r.right > innerWidth + 1 || r.left < -1); }).map(e => e.id || e.tagName);
          return { scroll: document.documentElement.scrollWidth, width: innerWidth, clipped };
        }""")
        assert result['scroll'] <= result['width'] + 1, result
        assert result['clipped'] == []
    finally:
        ctx.close()


@pytest.mark.parametrize('theme', THEMES)
def test_late_fonts_do_not_shift_layout_beyond_cls_budget(browser, server, theme):
    ctx = _context(browser, theme, MOBILE)
    ctx.add_init_script("""window.__cls = 0; new PerformanceObserver(l => { for (const e of l.getEntries())
        if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: 'layout-shift', buffered: true });""")
    page = ctx.new_page()
    delayed = []

    def slow_font(route):
        delayed.append(route.request.url)
        page.wait_for_timeout(0)
        import time
        time.sleep(.5)
        route.continue_()
    page.route('**/fonts/*.woff2', slow_font)
    try:
        page.goto(server['base'], wait_until='load')
        page.wait_for_timeout(1200)
        assert delayed, 'no font was delayed: the control did not exercise anything'
        assert page.evaluate('() => document.fonts.ready.then(() => window.__cls)') <= 0.1
    finally:
        ctx.close()


def _measure(browser, server, theme, profile, save_data=False):
    ctx = browser.new_context(**profile)
    ctx.add_init_script(f"try {{ localStorage.setItem('pbt-theme', '{theme}'); }} catch (_) {{}}"
                        "Object.defineProperty(navigator, 'hardwareConcurrency', {configurable: true, value: 8});")
    if save_data:
        ctx.add_init_script("Object.defineProperty(navigator, 'connection', {configurable: true, value: {saveData: true, effectiveType: '4g'}});")
    page = ctx.new_page()
    cdp = ctx.new_cdp_session(page)
    cdp.send('Network.enable')
    kinds, sizes = {}, {}
    cdp.on('Network.responseReceived', lambda e: kinds.__setitem__(e['requestId'], e['type']))
    cdp.on('Network.loadingFinished', lambda e: sizes.__setitem__(e['requestId'], e['encodedDataLength']))
    try:
        page.goto(server['base'], wait_until='load')
        page.wait_for_timeout(3000)
        totals = {'critical': 0, 'font': 0, 'image': 0, 'media': 0}
        names = {'Document': 'critical', 'Stylesheet': 'critical', 'Script': 'critical', 'Fetch': 'critical',
                 'Font': 'font', 'Image': 'image', 'Media': 'media'}
        for rid, size in sizes.items():
            totals[names.get(kinds.get(rid), 'critical')] += size
        preloads = page.evaluate("""() => [...document.querySelectorAll('link[rel=preload][as=video], link[rel=preload][as=audio]')].length""")
        return totals, preloads
    finally:
        ctx.close()


@pytest.mark.parametrize('theme', THEMES)
@pytest.mark.parametrize('name,profile,save_data', [('mobile', MOBILE, False), ('desktop', DESKTOP, False), ('save_data', MOBILE, True)],
                         ids=['mobile', 'desktop', 'save_data'])
def test_page_transfer_stays_within_predeclared_budget(browser, server, theme, name, profile, save_data):
    totals, preloads = _measure(browser, server, theme, profile, save_data)
    limits = BUDGET['limits_bytes'][name]
    over = {k: (v, limits[k]) for k, v in totals.items() if v > limits[k]}
    assert not over, f'{name}/{theme} over budget (measured, limit): {over}'
    assert totals['critical'] > 0, 'measurement saw no document: the gate measured nothing'
    assert preloads <= BUDGET['max_high_priority_media_preloads']
