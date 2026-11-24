"""«Гусениця» — фірмовий прогрес сторінки теми «Сталь»: золоті траки = пройдене, зірочка — на межі, станції секцій.

Інваріанти: прогрес = scrollY / (scrollHeight − innerHeight); ланцюг рухається лише за скролом;
reduced-motion — без інерції; у «Графіті» й у друку гусениці немає; декор недоступний для читачів екрана.
"""
import pytest


STATE = """() => { const t = document.getElementById('track'), cs = getComputedStyle(t), sp = t.querySelector('.track__sprocket').getBoundingClientRect();
  return {display: cs.display, tp: parseFloat(t.style.getPropertyValue('--tp') || '0'), tx: t.style.getPropertyValue('--tx'),
          up: t.classList.contains('is-up'), top: t.getBoundingClientRect().top, sprocket: sp.left + sp.width / 2,
          p: scrollY / (document.scrollingElement.scrollHeight - innerHeight), w: innerWidth,
          hidden: t.getAttribute('aria-hidden'), stops: [...t.querySelectorAll('#trackStops a')].map(a => a.getAttribute('href'))} }"""


def test_track_reports_true_progress_and_stations(page_factory):
    pg = page_factory(1440, 900, reduced=True)
    s = pg.evaluate(STATE)
    assert s['display'] == 'block' and s['hidden'] == 'true'
    assert s['stops'] == ['#roboty', '#tekhnika', '#cina', '#materialy', '#dokaz', '#geo', '#zapyt']
    for frac in (.25, .5, .9):
        pg.evaluate(f"scrollTo(0, (document.scrollingElement.scrollHeight - innerHeight) * {frac})")
        pg.wait_for_timeout(250)
        s = pg.evaluate(STATE)
        assert abs(s['tp'] - s['p']) < .002, s
        assert abs(s['sprocket'] - s['p'] * s['w']) <= 2, s               # зірочка стоїть точно на межі пройденого


def test_track_follows_the_nav_and_rolls_with_scroll(page_factory):
    pg = page_factory(1440, 900)
    pg.mouse.wheel(0, 3000)
    pg.wait_for_timeout(900)
    a = pg.evaluate(STATE)
    assert a['up'] and abs(a['top']) < 1, a                               # шапка сховалась — ланцюг біля краю екрана
    pg.mouse.wheel(0, 400)
    pg.wait_for_timeout(900)
    b = pg.evaluate(STATE)
    assert b['tx'] != a['tx'], (a, b)                                    # траки зсунулись разом зі сторінкою
    pg.mouse.wheel(0, -300)
    pg.wait_for_timeout(900)
    c = pg.evaluate(STATE)
    assert not c['up'] and c['top'] > 30, c                              # шапка повернулась — ланцюг під нею


def test_reduced_motion_has_no_inertia(page_factory):
    pg = page_factory(1440, 900, reduced=True)
    pg.evaluate("scrollTo(0, 4000)")
    pg.wait_for_timeout(60)                                               # два кадри: без інерції ланцюг уже на місці
    first = pg.evaluate(STATE)['tx']
    pg.wait_for_timeout(500)
    assert pg.evaluate(STATE)['tx'] == first


@pytest.mark.parametrize('media', ['precision', 'print'])
def test_track_absent_in_graphite_and_print(page_factory, media):
    pg = page_factory(1440, 900)
    if media == 'precision':
        pg.locator('[data-theme-choice="precision"]').click()
    else:
        pg.emulate_media(media='print')
    assert pg.evaluate("getComputedStyle(document.getElementById('track')).display") == 'none'


OIL_INK = """() => { const c = document.getElementById('trackOil'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
  let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 8) n++; return n }"""


def test_oil_drips_only_while_rolling_and_then_dries(page_factory):
    pg = page_factory(1440, 900)
    assert pg.evaluate(OIL_INK) == 0                                        # спокій — жодної краплі
    for _ in range(6):
        pg.mouse.wheel(0, 260)
        pg.wait_for_timeout(40)
    pg.wait_for_timeout(150)
    assert pg.evaluate(OIL_INK) > 0                                         # ланцюг котиться — масло тече (крапля щойно набрякає: кілька пікселів)
    pg.wait_for_timeout(2600)
    assert pg.evaluate(OIL_INK) == 0                                        # краплі тануть, rAF засинає


def test_no_oil_under_reduced_motion(page_factory):
    pg = page_factory(1440, 900, reduced=True)
    for _ in range(6):
        pg.mouse.wheel(0, 260)
        pg.wait_for_timeout(40)
    pg.wait_for_timeout(150)
    assert pg.evaluate(OIL_INK) == 0
