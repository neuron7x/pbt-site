"""«Сталь і золото»: вади, які пройшли повний гейт і знайшла лише незалежна рецензія (dfdd532).

На CSS до виправлення (bf9a335) червоніють 7 із 15 випадків — по кожному класу вади: натиснута кнопка руху 1,37:1,
фокус «Заявки» 1,6:1 (обидві теми), підпис глибиноміра 2,53:1 на світлих секціях, заповнювач «S .» у CSS.
Оракул контрасту й випадки, що були справні до виправлення (темні секції, панель на телефоні), лишаються зеленими.
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


def test_gauge_depth_label_is_removed_in_steel_theme(page_factory):
    """Слово власника 25.11.2026: підпис глибини під гаком прибрано. До того тут перевірялась читабельність підпису над
    кожною секцією (bf9a335: 3 світлі секції 2,5–2,8:1); об'єкта перевірки більше немає, тож вимога — що його справді
    не видно ні над світлою, ні над темною секцією, а сам глибиномір лишається."""
    pg = page_factory(1366, 768, reduced=True)
    pg.locator('[data-theme-choice="sky"]').click()
    for section in ('roboty', 'tekhnika', 'zapyt'):
        pg.evaluate(f"document.getElementById('{section}').scrollIntoView({{behavior:'instant', block:'center'}})")
        pg.wait_for_timeout(300)
        assert not pg.locator('.gauge__m').is_visible(), section
        assert pg.locator('#gauge').is_visible(), section


def test_hook_picks_up_the_load_at_page_bottom_and_carries_it_back_up(page_factory):
    """Гак опускається з прокруткою; унизу сторінки підчіплює вантаж і далі несе його. Стан не скидається дорогою вгору."""
    pg = page_factory(1440, 900, reduced=True)
    pg.locator('[data-theme-choice="sky"]').click()
    state = "({load: document.getElementById('gauge').classList.contains('has-load')," \
            " ground: getComputedStyle(document.getElementById('gauge'), '::after').display," \
            " carried: getComputedStyle(document.querySelector('.gauge__float'), '::after').content," \
            " y: new DOMMatrix(getComputedStyle(document.querySelector('.gauge__float')).transform).m42," \
            " h: document.getElementById('gauge').clientHeight})"
    pg.evaluate("window.scrollTo(0, (document.documentElement.scrollHeight - innerHeight) * 0.5)")
    pg.wait_for_timeout(400)
    mid = pg.evaluate(state)
    assert mid['load'] is False and mid['ground'] == 'block' and mid['carried'] == 'none', mid   # вантаж стоїть унизу, гак порожній
    assert 0.4 * mid['h'] < mid['y'] < 0.6 * mid['h'], mid
    pg.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    pg.wait_for_timeout(400)
    bottom = pg.evaluate(state)
    assert bottom['load'] is True and bottom['ground'] == 'none' and bottom['carried'] != 'none', bottom
    assert bottom['y'] > 0.97 * bottom['h'], bottom
    pg.evaluate("window.scrollTo(0, (document.documentElement.scrollHeight - innerHeight) * 0.1)")
    pg.wait_for_timeout(400)
    up = pg.evaluate(state)
    assert up['load'] is True and up['ground'] == 'none' and up['carried'] != 'none', up            # вантаж їде вгору разом із гаком
    assert up['y'] < 0.2 * up['h'], up


def test_hook_load_is_hidden_on_short_viewports_and_in_graphite(page_factory):
    pg = page_factory(1366, 600, reduced=True)
    pg.locator('[data-theme-choice="sky"]').click()
    assert pg.evaluate("getComputedStyle(document.getElementById('gauge'), '::after').display") == 'none'
    pg.locator('[data-theme-choice="precision"]').click()
    assert pg.evaluate("getComputedStyle(document.getElementById('gauge')).display") == 'none'
