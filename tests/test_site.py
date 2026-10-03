"""Браузерні перевірки: верстка на 3 в'юпортах, сцена героя, парк, калькулятор, форма до сервера, WCAG 2.2 AA (axe)."""
import json, re, sqlite3
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
VIEWPORTS = [(1440, 900, False), (820, 1180, True), (390, 844, True)]
DATA = json.loads(re.search(r'window\.PBT = (\{.*\});', (ROOT / 'web' / 'js' / 'data.js').read_text(encoding='utf-8'), re.S).group(1))
VECTORS = json.loads((ROOT / 'tests' / 'contracts' / 'lead_vectors.json').read_text(encoding='utf-8'))['vectors']


def no_overflow(pg):
    return pg.evaluate('document.scrollingElement.scrollWidth <= innerWidth + 1')


@pytest.mark.parametrize('w,h,mobile', VIEWPORTS, ids=lambda v: str(v))
def test_layout_no_horizontal_scroll_and_no_errors(page_factory, w, h, mobile):
    pg = page_factory(w, h, mobile=mobile)
    assert no_overflow(pg), 'горизонтальний скрол на старті'
    for y in (0.5, 1.5, 3, 6, 10):
        pg.evaluate(f'scrollTo({{top: innerHeight * {y}, behavior: "instant"}})'); pg.wait_for_timeout(250)
        assert no_overflow(pg), f'горизонтальний скрол на {y} екранах'
    assert pg.locator('h1').is_visible() or pg.evaluate('scrollY') > 0
    errs = [e for e in pg.errors if 'favicon' not in e]
    assert not errs, errs


def test_fleet_renders_every_unit_and_chips_filter(page_factory):
    pg = page_factory()
    assert pg.locator('#park .unit').count() == len(DATA['fleet']) == 32
    pg.click('#chips .chip[data-cat="amph"]')
    visible = pg.locator('#park .unit:not([hidden])').count()
    assert visible == sum(1 for u in DATA['fleet'] if u['cat'] == 'amph') == 4
    pg.click('#chips .chip[data-cat="all"]')
    assert pg.locator('#park .unit:not([hidden])').count() == 32


def test_calculator_matches_price_list(page_factory):
    pg = page_factory()
    priced = [u for u in DATA['fleet'] if u['price'] and u['unit'] == 'год']
    u = next(x for x in priced if x['id'] == 'e-1')                      # JCB JS220LC, 22 т → трал 40 т (100 грн/км)
    pg.select_option('#cMachine', u['id'])
    pg.fill('#cHoursN', '10'); pg.dispatch_event('#cHoursN', 'input')
    pg.fill('#cKmN', '20'); pg.dispatch_event('#cKmN', 'input')
    expected = 10 * u['price'] + 20 * 100
    assert pg.evaluate('document.getElementById("cOut").dataset.total') == str(expected)
    digits = re.sub(r'\D', '', pg.inner_text('#cTotal'))
    assert digits == str(expected)
    assert pg.evaluate(f'window.PBTcalc("{u["id"]}", 10, 20)') == expected
    crane = next(x for x in priced if x['cat'] == 'crane')               # автокран їде сам: подача не рахується за км
    pg.select_option('#cMachine', crane['id'])
    assert pg.evaluate('document.getElementById("cKmN").disabled') is True
    assert pg.evaluate(f'window.PBTcalc("{crane["id"]}", 10, 20)') == 10 * crane['price']
    heavy = next(x for x in priced if x['id'] == 'e-3')                 # DOOSAN DX300, 31 т → також трал 40 т
    assert pg.evaluate(f'window.PBTcalc("{heavy["id"]}", 1, 10)') == heavy['price'] + 10 * 100


@pytest.mark.parametrize('v', VECTORS, ids=lambda v: f"{v['field']}:{v['value']}")
def test_contract_vectors_client(page_factory, v):
    """Клієнт і сервер валідують за одним корпусом (tests/contracts/lead_vectors.json)."""
    pg = page_factory()
    ok = pg.evaluate('([f, val, t, m]) => window.PBTv(f, val, t, m)', [v['field'], v['value'], v['type'], v.get('method')])
    assert ok is v['valid'], v


def test_lead_form_submits_to_server_and_is_stored(page_factory, server):
    pg = page_factory(390, 844, mobile=True)
    pg.click('#park .unit[data-id="pe-1"] [data-req]')                   # «У заявку» → тип і предмет заповнені
    pg.wait_for_timeout(900)
    assert pg.input_value('#subject').startswith('Плаваючий екскаватор-амфібія')
    pg.fill('#hours', '16'); pg.fill('#km', '40'); pg.fill('#place', 'Полтава, Левада'); pg.fill('#name', 'Тест'); pg.fill('#contact', '097 863 77 77')
    pg.click('#send')
    pg.wait_for_selector('#done.is-on', timeout=5000)
    ref = pg.inner_text('#ref')
    assert re.fullmatch(r'PBT-\d{6}', ref)
    row = sqlite3.connect(server['db']).execute('select payload from leads order by id desc limit 1').fetchone()
    d = json.loads(row[0])
    assert d['type'] == 'rent' and d['hours'] == 16 and d['km'] == 40 and d['contact'] == '+380978637777'
    assert d['subject'].startswith('Плаваючий екскаватор-амфібія')


def test_lead_form_shows_field_errors_before_sending(page_factory):
    pg = page_factory()
    pg.fill('#contact', '12345'); pg.fill('#hours', '0')
    pg.click('#send')
    assert pg.locator('[data-field="contact"].is-err').count() == 1
    assert pg.locator('[data-field="hours"].is-err').count() == 1
    assert pg.locator('#done.is-on').count() == 0


def test_hero_scene_scrubs_frames_on_desktop(page_factory):
    pg = page_factory()
    poster = pg.get_attribute('#heroSeq', 'src')
    assert poster.endswith('poster.webp') or poster.endswith('f_001.webp')   # перший декодований кадр уже міг підмінити постер
    pg.evaluate('scrollTo({top: innerHeight * 1.4, behavior: "instant"})')
    pg.wait_for_function('document.getElementById("heroSeq").src.includes("/media/hero/f_")', timeout=10000)
    wl = float(pg.evaluate('getComputedStyle(document.getElementById("heroWater")).getPropertyValue("--wl")') or 0)
    assert 0 <= wl < 1
    pg.evaluate('scrollTo({top: innerHeight * 2.25, behavior: "instant"})'); pg.wait_for_timeout(300)   # html має scroll-behavior:smooth — тест скролить миттєво
    wl2 = float(pg.evaluate('getComputedStyle(document.getElementById("heroWater")).getPropertyValue("--wl")'))
    assert wl2 > 0.9, wl2                                                 # наприкінці герой затоплений — перехід у синю секцію
    assert pg.evaluate('document.getElementById("gauge").classList.contains("is-on")')


def test_reduced_motion_is_static_but_complete(page_factory):
    pg = page_factory(reduced=True)
    assert pg.evaluate('document.documentElement.dataset.quality') == 'static'
    assert pg.get_attribute('#heroSeq', 'src').endswith('poster.webp')
    assert pg.locator('h1').is_visible() and pg.locator('#park .unit').count() == 32


def test_mobile_menu_opens_and_closes(page_factory):
    pg = page_factory(390, 844, mobile=True)
    assert pg.locator('#menu').is_hidden()
    pg.click('.burger'); assert pg.locator('#menu').is_visible()
    pg.click('#menu a[href="#tekhnika"]'); pg.wait_for_timeout(400)
    assert pg.locator('#menu').is_hidden()


def test_geo_map_marks_home_and_served(page_factory):
    pg = page_factory()
    assert pg.locator('#geoMap .obl').count() >= 25
    assert pg.locator('#geoMap .obl.served').count() == len(DATA['regions']) + 1   # + м. Київ як окремий контур у Київській
    assert pg.locator('#geoMap .obl.home').count() == 1


def test_404_page(page_factory):
    pg = page_factory(path='/nema-takoi-storinky')
    assert '404' in pg.inner_text('main') and 'Сторінки немає' in pg.title()


@pytest.mark.parametrize('w,h,mobile', VIEWPORTS[::2], ids=lambda v: str(v))
def test_axe_wcag22aa_no_serious_violations(page_factory, w, h, mobile):
    pg = page_factory(w, h, mobile=mobile, bypass_csp=True)
    pg.add_script_tag(path=str(ROOT / 'tests' / 'vendor' / 'axe.min.js'))
    res = pg.evaluate('axe.run(document, {runOnly: {type: "tag", values: ["wcag2a", "wcag2aa", "wcag22aa"]}})')
    bad = [(v['id'], v['impact'], [n['target'] for n in v['nodes']][:3]) for v in res['violations'] if v['impact'] in ('serious', 'critical')]
    assert not bad, bad
