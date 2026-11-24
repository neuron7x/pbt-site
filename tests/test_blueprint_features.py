"""Креслення техніки, паспорт машини, виліт стріли крана, маршрути доставки.

Інваріанти:
- на кресленні немає вигаданих чисел: кожне число у підписах (крім живого вильоту) є в характеристиках каталогу;
- виліт рахується як r = L·cos θ, h = L·sin θ від довжини стріли з каталогу;
- ціна подачі в панелі маршруту = км × ставка тралу (та сама модель, що й калькулятор);
- паспорт — модальний діалог: фокус усередині, Esc закриває й повертає фокус, axe без порушень.
"""
import math
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NUM = re.compile(r'\d+(?:[.,]\d+)?')


def _data(page):
    return page.evaluate('window.PBT')


def _module(page):
    """Модуль креслень вантажиться ліниво (поза критичним бюджетом) — для чистих функцій підвантажуємо його явно."""
    assert page.evaluate('typeof window.PBTBlueprint') == 'undefined', 'креслення не мають їхати до наміру'
    page.add_script_tag(url='js/blueprint.js')
    page.locator('script[src="js/blueprint.js"]').wait_for(state='attached')
    for _ in range(50):
        if page.evaluate('!!window.PBTBlueprint'):
            break
        page.wait_for_timeout(50)
    return page


def test_every_fleet_unit_has_a_drawing_without_invented_numbers(page_factory):
    pg = _module(page_factory(1440, 900))
    res = pg.evaluate("""() => PBT.fleet.map(u => {
        const r = PBTBlueprint.draw(u); if (!r) return {id: u.id, ok: false};
        const texts = [...r.svg.querySelectorAll('text')].filter(t => !t.closest('.bp-live')).map(t => t.textContent);
        return {id: u.id, ok: true, kind: r.kind, paths: r.svg.querySelectorAll('path').length, texts,
                specs: u.specs.map(s => s.v).join(' | '), label: r.svg.getAttribute('aria-label')} })""")
    assert len(res) == len(_data(pg)['fleet']) == 32
    for r in res:
        assert r['ok'], r
        assert r['paths'] >= 10, r
        assert r['label'].startswith('Креслення: '), r
        allowed = set(NUM.findall(r['specs']))
        for text in r['texts']:
            for n in NUM.findall(text):
                assert n in allowed, (r['id'], text, r['specs'])          # ціле число-токен, не підрядок («2» ≠ «22»)


def test_reach_geometry_matches_formula_and_rejects_nonsense(page_factory):
    pg = _module(page_factory(1440, 900))
    for boom, angle in [(22, 0), (42, 38), (60, 45), (70, 80), (16.5, 90)]:
        got = pg.evaluate(f'PBTBlueprint.reach({boom}, {angle})')
        a = math.radians(angle)
        assert got == {'r': round(boom * math.cos(a), 1), 'h': round(boom * math.sin(a), 1)}, (boom, angle, got)
    for bad in ['0, 30', '-5, 30', '42, -1', '42, 91', 'NaN, 10', 'null, 10']:
        assert pg.evaluate(f'PBTBlueprint.reach({bad})') is None, bad
    assert pg.evaluate("PBTBlueprint.meters('16,5 м')") == 16.5
    assert pg.evaluate("PBTBlueprint.meters('22 т')") is None


@pytest.mark.parametrize('theme', ['sky', 'precision'])
def test_passport_is_a_modal_sheet_with_catalog_specs(page_factory, theme):
    pg = page_factory(1440, 900)
    pg.locator(f'[data-theme-choice="{theme}"]').click()
    unit = next(u for u in _data(pg)['fleet'] if u['id'] == 'e-3')
    opener = pg.locator('.unit[data-id="e-3"] .unit__pass')
    opener.focus()
    pg.keyboard.press('Enter')
    pg.locator('#passport[open]').wait_for()
    state = pg.evaluate("""() => { const d = document.getElementById('passport');
        return {open: d.open, modal: d.matches(':modal'), inside: d.contains(document.activeElement),
                title: document.getElementById('passTitle').textContent,
                stamp: [...d.querySelectorAll('#passStamp tr')].map(tr => [tr.cells[0].textContent, tr.cells[1].textContent]),
                svg: !!d.querySelector('#passDraw svg.bp'), reach: document.getElementById('passReach').hidden} }""")
    assert state['open'] and state['modal'] and state['inside'], state
    assert state['title'] == unit['name'] and state['svg'] and state['reach'], state
    stamp = dict(state['stamp'])
    for s in unit['specs']:
        assert stamp[s['k']] == s['v'], (s, stamp)
    assert stamp['Ставка'] == '1 500 грн/год', stamp
    pg.keyboard.press('Escape')
    pg.wait_for_timeout(200)
    assert not pg.evaluate("document.getElementById('passport').open")
    assert pg.evaluate("document.activeElement.dataset.pass") == 'e-3'


def test_crane_passport_reach_follows_the_slider(page_factory):
    pg = page_factory(1440, 900)
    unit = next(u for u in _data(pg)['fleet'] if u['id'] == 'ak-2')
    boom = float(next(s['v'] for s in unit['specs'] if 'стріл' in s['k']).split()[0].replace(',', '.'))
    pg.locator('.unit[data-id="ak-2"] .unit__pass').click()
    pg.locator('#passport[open]').wait_for()
    assert pg.locator('#passReach').is_visible()
    for angle in (0, 38, 65, 80):
        pg.locator('#passAngle').fill(str(angle))
        out = pg.locator('#passReachOut').text_content().replace(' ', ' ')
        r, h = round(boom * math.cos(math.radians(angle)), 1), round(boom * math.sin(math.radians(angle)), 1)
        want = f"Виліт {str(r).replace('.', ',').removesuffix(',0')} м"
        assert out.startswith(want), (angle, out, want)
        assert f"оголовок на {str(h).replace('.', ',').removesuffix(',0')} м вище п’яти стріли" in out, (angle, out)
        assert pg.locator('#passAngleOut').text_content() == f'{angle}°'
        tip = pg.evaluate("""() => { const b = document.querySelector('#passDraw .bp-boom').getBBox(),
            v = document.querySelector('#passDraw svg').viewBox.baseVal; return {top: b.y, vtop: v.y} }""")
        assert tip['top'] >= tip['vtop'], (angle, tip)            # стріла не виходить за аркуш на жодному куті


def test_passport_request_button_closes_and_fills_the_form(page_factory):
    pg = page_factory(1440, 900)
    pg.locator('.unit[data-id="tr-2"] .unit__pass').click()
    pg.locator('#passport[open]').wait_for()
    pg.locator('#passReq').click()
    pg.wait_for_timeout(600)
    assert not pg.evaluate("document.getElementById('passport').open")
    assert pg.locator('#subject').input_value() == next(u['name'] for u in _data(pg)['fleet'] if u['id'] == 'tr-2')
    assert pg.locator('input[name="type"][value="transport"]').is_checked()


def test_passport_print_shows_only_the_sheet(page_factory):
    pg = page_factory(1440, 900)
    pg.locator('.unit[data-id="pe-1"] .unit__pass').click()
    pg.locator('#passport[open]').wait_for()
    pg.emulate_media(media='print')
    hidden = pg.evaluate("""() => [...document.body.children].filter(e => e.id !== 'passport')
        .every(e => getComputedStyle(e).display === 'none')""")
    assert hidden
    assert pg.evaluate("getComputedStyle(document.querySelector('.pass__act')).display") == 'none'


def test_open_passport_has_zero_axe_violations(page_factory):
    pg = page_factory(1440, 900, bypass_csp=True)
    pg.locator('.unit[data-id="ak-3"] .unit__pass').click()
    pg.locator('#passport[open]').wait_for()
    pg.add_script_tag(path=str(ROOT / 'tests' / 'vendor' / 'axe.min.js'))
    pg.add_style_tag(content='*,*::before,*::after{transition:none!important;animation:none!important}')
    res = pg.evaluate('axe.run(document.getElementById("passport"), {runOnly: {type: "tag", values: '
                      '["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]}})')
    bad = [(v['id'], [n['target'] for n in v['nodes']][:3]) for v in res['violations']]
    assert not bad, bad


def test_xray_draws_on_hover_only_for_fine_pointer(page_factory):
    pg = page_factory(1440, 900, reduced=True)
    pg.evaluate("document.getElementById('tekhnika').scrollIntoView({behavior:'instant'})")
    fig = pg.locator('.unit[data-id="b-3"] figure')
    assert pg.evaluate("document.querySelector('.unit[data-id=\"b-3\"] .unit__bp').childElementCount") == 0   # ліниво: DOM не росте
    assert pg.evaluate('typeof window.PBTBlueprint') == 'undefined'
    fig.hover()
    pg.wait_for_selector('.unit[data-id="b-3"] .unit__bp svg.bp', state='attached')
    assert pg.evaluate("document.querySelector('.unit[data-id=\"b-3\"] .unit__bp svg.bp') !== null")
    assert pg.evaluate("getComputedStyle(document.querySelector('.unit[data-id=\"b-3\"] .unit__bp')).clipPath") == 'inset(0px)'
    mob = page_factory(390, 844, mobile=True)
    mob.evaluate("document.getElementById('tekhnika').scrollIntoView({behavior:'instant'})")
    mob.locator('.unit[data-id="b-3"] figure img').tap()
    mob.wait_for_timeout(300)
    assert mob.evaluate("document.querySelector('.unit[data-id=\"b-3\"] .unit__bp').childElementCount") == 0


def test_route_panel_prices_delivery_like_the_calculator(page_factory):
    pg = page_factory(1440, 900)
    pg.evaluate("document.getElementById('geo').scrollIntoView({behavior:'instant'})")
    pg.locator('#geoMap svg[data-ready="1"]').wait_for(state='attached')   # контури карти — ліниві дані
    D = _data(pg)
    served = [r for r in D['regions'] if r != 'Полтавська']
    assert set(served) == set(D['routes']['to']), 'кожна область виїзду має дорожню відстань'
    assert re.fullmatch(r'\d{4}-\d{2}-\d{2}', D['routes']['date']) and 'OpenStreetMap' in D['routes']['source']
    for region in served:
        km = D['routes']['to'][region]['km']
        assert 50 <= km <= 700, (region, km)
        pg.locator(f'.geo__pick[data-ua="{region}"]').click()
        assert pg.locator(f'.geo__pick[data-ua="{region}"]').get_attribute('aria-pressed') == 'true'
        assert re.sub(r'\s', '', pg.locator('#geoInfo .geo__km b').text_content()) == str(km)
        costs = [re.sub(r'\s', '', c) for c in pg.locator('#geoInfo .geo__cost dd').all_text_contents()]
        assert costs == [f"≈{t['rate'] * km}грн" for t in sorted(D['trailers'], key=lambda t: t['maxT'])], costs
        assert pg.evaluate(f"document.querySelector('.route.is-sel').dataset.ua") == region
    # та сама модель, що й калькулятор: доставка з PBTQuote для 22-тонного екскаватора = рядок «Трал 40 т» панелі
    e1 = next(u for u in D['fleet'] if u['id'] == 'e-1')
    for region, r in D['routes']['to'].items():
        q = pg.evaluate(f"PBTQuote.quote(PBT.fleet.find(u => u.id === 'e-1'), PBT.trailers, 1, {r['km']})")
        pg.locator(f'.geo__pick[data-ua="{region}"]').click()
        row = re.sub(r'\s', '', pg.locator('#geoInfo .geo__cost div').first.text_content())
        assert q['status'] == 'complete' and row.endswith(f"≈{q['delivery']}грн"), (region, q, row)
        assert q['trailer']['name'] in pg.locator('#geoInfo .geo__cost dt').first.text_content().replace('\u00a0', ' ')
    assert e1['specs'][0]['k'] == 'Маса'
    pg.locator('.geo__pick[data-ua="Київська"]').click()
    pg.locator('.geo__calc').click()
    pg.wait_for_timeout(800)
    assert pg.locator('#cKmN').input_value() == str(D['routes']['to']['Київська']['km'])
    assert pg.evaluate('document.activeElement.id') == 'cKmN'
    # повзунок (крок 5 км) стоїть на найближчій поділці до відстані, а не впирається в межу 300
    assert abs(int(pg.locator('#cKm').input_value()) - int(pg.locator('#cKmN').input_value())) <= 2.5
    # автокран: подача не тралом — фокус на вибір машини, а не «нічого не сталось»
    crane = pg.evaluate("[...document.querySelectorAll('#cMachine option')].findIndex(o => /Автокран/.test(o.textContent))")
    pg.select_option('#cMachine', index=crane)
    pg.evaluate("document.getElementById('geo').scrollIntoView({behavior:'instant'})")
    pg.locator('.geo__pick[data-ua="Житомирська"]').click()
    pg.locator('.geo__calc').click()
    pg.wait_for_timeout(800)
    assert pg.evaluate('document.activeElement.id') == 'cMachine'


def test_passport_close_stays_reachable_and_page_does_not_scroll_under_it(page_factory):
    pg = page_factory(320, 568, mobile=True)
    pg.evaluate("document.getElementById('tekhnika').scrollIntoView({behavior:'instant'})")
    pg.locator('.unit[data-id="ak-2"] .unit__pass').click()
    pg.locator('#passport[open]').wait_for()
    y0 = pg.evaluate('scrollY')                                          # після кліку: Playwright сам докручує до кнопки
    pg.evaluate("document.getElementById('passport').scrollTop = 99999")
    pg.wait_for_timeout(200)
    box = pg.locator('.pass__x').bounding_box()
    assert box and box['y'] >= 0 and box['y'] + box['height'] <= 568, box
    pg.mouse.move(4, 300)                                                 # смуга фону (::backdrop) поза аркушем
    pg.mouse.wheel(0, 800)
    pg.wait_for_timeout(300)
    assert pg.evaluate('scrollY') == y0
    pg.locator('.pass__x').click()
    assert not pg.evaluate("document.getElementById('passport').open")


def test_failed_drawing_load_falls_back_to_the_request_form(page_factory):
    pg = page_factory(1440, 900)
    pg.route('**/js/blueprint.js', lambda route: route.abort())
    pg.locator('.unit[data-id="e-2"] .unit__pass').click()
    pg.wait_for_timeout(800)
    assert not pg.evaluate("document.getElementById('passport').open")
    assert pg.locator('#subject').input_value() == next(u['name'] for u in _data(pg)['fleet'] if u['id'] == 'e-2')
    assert pg.evaluate('document.querySelectorAll(\'script[src="js/blueprint.js"]\').length') == 0
    pg.errors.clear()                                                   # навмисний обрив — не помилка сторінки
