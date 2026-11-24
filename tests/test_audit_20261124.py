"""Знахідки незалежного аудиту 24.11.2026 (ORDER_SITE_20261124.md), закриті кодом: кожна — тестом, що червоніє на старому коді.

п.14 — зупинки глибиноміра зіставлялись із секціями за індексом (9 секцій, 8 зупинок): «Техніка» стояла на «Масштабі».
п.41 — області поза зоною виїзду показувались англійською («Kherson Oblast — за запитом»).
п.42 — клас креслення «Каток» (ковзанка) замість «Коток» (дорожня машина).
"""


def test_gauge_stops_sit_on_their_own_sections(page_factory):
    pg = page_factory(1440, 900)
    rows = pg.evaluate("""() => { const max = document.scrollingElement.scrollHeight - innerHeight;
      return [...document.querySelectorAll('.gauge__stops li')].map(li => { const id = li.firstElementChild.getAttribute('href').slice(1);
        return {id, top: parseFloat(li.style.top), want: Math.min(1, Math.max(0, document.getElementById(id).offsetTop / max)) * 100}; }) }""")
    assert len(rows) == 8
    for r in rows:
        assert abs(r['top'] - r['want']) < 0.05, r


def test_unserved_regions_are_named_in_ukrainian(page_factory):
    pg = page_factory(1440, 900)
    pg.evaluate("document.getElementById('geo').scrollIntoView({behavior:'instant'})")
    names = pg.evaluate("[...document.querySelectorAll('#geoMap .obl:not([data-ua=\"\"])')].length")
    assert names >= 9
    seen = []
    for name in ['Kherson Oblast', 'Lviv Oblast', 'Autonomous Republic of Crimea']:
        pg.locator(f'#geoMap .obl[data-name="{name}"]').first.dispatch_event('pointerover')
        text = pg.locator('#geoHover').text_content()
        seen.append(text)
        assert not any(c.isascii() and c.isalpha() for c in text), text   # жодної латиниці
        assert text.endswith('— за запитом'), text
    assert seen[0].startswith('Херсонська') and seen[2].startswith('Автономна Республіка Крим'), seen


def test_road_roller_is_kotok(page_factory):
    pg = page_factory(1440, 900, bypass_csp=True)
    pg.add_script_tag(url='js/blueprint.js')
    for _ in range(50):
        if pg.evaluate('!!window.PBTBlueprint'):
            break
        pg.wait_for_timeout(50)
    assert pg.evaluate("PBTBlueprint.CLASS.roller") == 'Коток'
