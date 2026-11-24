"""«Сталь і золото»: вади, які пройшли повний гейт і знайшла лише незалежна рецензія (dfdd532).

Кожен тест червоніє на CSS до виправлення (bf9a335): натиснута кнопка руху 1,37:1,
фокус «Заявки» 1,6:1, підпис глибиноміра 2,53:1, неопрацьований заповнювач «S .» у CSS.
"""
import io
import pathlib
import re

import pytest

CSS = pathlib.Path(__file__).resolve().parents[1] / 'web' / 'css' / 'site.css'


def _rgb(value):
    return tuple(int(v) for v in re.findall(r'\d+', value)[:3])


def _lum(rgb):
    v = [c / 255 for c in rgb]
    v = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in v]
    return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]


def _ratio(a, b):
    lo, hi = sorted((_lum(a), _lum(b)))
    return (hi + .05) / (lo + .05)


def test_oracle_matches_known_pairs():
    assert round(_ratio((6, 43, 92), (11, 16, 23)), 2) == 1.37
    assert round(_ratio((255, 255, 255), (253, 197, 1)), 1) == 1.6
    assert _ratio((11, 16, 23), (253, 197, 1)) > 11


def test_layer_has_no_unsubstituted_placeholder():
    """Шар генерується з «S» → селектор теми; пропущене «S .x» — мертве правило без помилки."""
    tail = CSS.read_text(encoding='utf-8').split('«СТАЛЬ І ЗОЛОТО»', 1)[1]
    assert not re.search(r'(^|[\s,{}(])S \.', tail, re.M)


@pytest.mark.parametrize('theme', ['sky', 'precision'])
@pytest.mark.parametrize('w,h,mobile', [(1366, 768, False), (390, 844, True)])
def test_pressed_motion_toggle_stays_readable(page_factory, theme, w, h, mobile):
    pg = page_factory(w, h, mobile=mobile)
    pg.locator(f'[data-theme-choice="{theme}"]').click()
    pg.locator('#motionToggle').click()
    s = pg.evaluate("""() => { const t = document.getElementById('motionToggle'), c = getComputedStyle(t);
        return {pressed: t.getAttribute('aria-pressed'), bg: c.backgroundColor, fg: c.color} }""")
    assert s['pressed'] == 'true', s
    assert 'rgba' not in s['bg'], s                                        # непрозорий фон — інакше пара не визначена
    assert _ratio(_rgb(s['fg']), _rgb(s['bg'])) >= 4.5, s


@pytest.mark.parametrize('theme', ['sky', 'precision'])
@pytest.mark.parametrize('sel', ['.dock__call', '.dock__go'])
def test_dock_focus_ring_contrasts_with_its_own_fill(page_factory, theme, sel):
    """Обвідка всередині кнопки (offset < 0) лежить на її фоні; WCAG 1.4.11 / 2.4.11 — ≥ 3:1."""
    pg = page_factory(390, 844, mobile=True)
    pg.locator(f'[data-theme-choice="{theme}"]').click()
    pg.focus(sel)
    pg.keyboard.press('Shift+Tab')
    pg.keyboard.press('Tab')
    s = pg.evaluate(f"""() => {{ const a = document.querySelector('{sel}'), c = getComputedStyle(a);
        let bg = c.backgroundColor;
        if (bg === 'rgba(0, 0, 0, 0)') bg = getComputedStyle(document.getElementById('dock')).backgroundColor;
        return {{focused: document.activeElement === a, visible: a.matches(':focus-visible'), style: c.outlineStyle,
                 ring: c.outlineColor, width: parseFloat(c.outlineWidth), bg}} }}""")
    assert s['focused'] and s['visible'], s
    assert s['style'] != 'none' and s['width'] >= 2, s
    assert _ratio(_rgb(s['ring']), _rgb(s['bg'])) >= 3, s


@pytest.mark.parametrize('section', ['roboty', 'tekhnika', 'cina', 'materialy', 'zapyt'])
def test_gauge_depth_label_readable_over_every_section(page_factory, section):
    """Підпис глибиноміра фіксований і пливе над темними й світлими секціями.
    Вимір пікселями: текст сховано, 90-й перцентиль і 10-й перцентиль яскравості фону під ним проти кольору тексту.
    Лише «Сталь»: у «Графіті» підпис змішується (mix-blend), обчислений колір ≠ відмальований."""
    from PIL import Image
    pg = page_factory(1366, 768, reduced=True)
    pg.locator('[data-theme-choice="sky"]').click()
    assert pg.evaluate(f"!!document.getElementById('{section}')"), section
    pg.evaluate(f"document.getElementById('{section}').scrollIntoView({{behavior:'instant', block:'center'}})")
    pg.wait_for_timeout(700)
    label = pg.locator('.gauge__m')
    assert label.is_visible()
    fg = _rgb(pg.evaluate("getComputedStyle(document.querySelector('.gauge__m')).color"))
    pg.add_style_tag(content='.gauge__m{color:transparent!important;text-shadow:none!important}')
    pg.wait_for_timeout(100)
    im = Image.open(io.BytesIO(pg.screenshot(clip=label.bounding_box()))).convert('RGB')
    ls = sorted(_lum(px) for px in im.getdata())
    fl = _lum(fg)
    for bg in (ls[int(len(ls) * .1)], ls[int(len(ls) * .9)]):
        r = (max(fl, bg) + .05) / (min(fl, bg) + .05)
        assert r >= 4.5, (section, fg, round(r, 2))
