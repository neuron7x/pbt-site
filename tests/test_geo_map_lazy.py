"""Карта областей поза критичним шляхом: 30,5 КБ gzip контурів більше не в HTML, а в media/map/oblasts.json.

Інваріанти: (1) до наближення секції жодного запиту карти і жодного контуру; (2) після — 27 контурів, 8 маршрутів, центри
з даних збігаються з геометрією контурів (tools/geo_map.py); (3) вибір області до приходу карти застосовується, щойно вона
приходить; (4) рамка SVG стоїть з першого кадру (viewBox) — секція не стрибає; (5) інструмент перевірки зелений.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_map_is_not_on_the_critical_path_and_arrives_near_the_section(page_factory):
    pg = page_factory(1440, 900)
    seen = []
    pg.on('request', lambda r: seen.append(r.url) if 'oblasts.json' in r.url else None)
    pg.wait_for_timeout(800)
    assert not seen and pg.locator('#geoMap .obl').count() == 0
    box0 = pg.locator('#geoMap svg').bounding_box()
    assert box0 and box0['height'] > 100                                    # рамка з viewBox тримає місце
    pg.evaluate("document.getElementById('geo').scrollIntoView({behavior:'instant'})")
    pg.locator('#geoMap svg[data-ready="1"]').wait_for(state='attached')
    assert len(seen) == 1
    assert pg.locator('#geoMap .obl').count() == 27 and pg.locator('#geoMap .route').count() == 8
    assert abs(pg.locator('#geoMap svg').bounding_box()['height'] - box0['height']) < 1   # без зсуву розкладки


def test_selection_made_before_the_map_arrives_is_applied(page_factory):
    pg = page_factory(1440, 900)
    pg.route('**/media/map/oblasts.json', lambda route: (pg.wait_for_timeout(1200), route.continue_()))
    pg.locator('.geo__pick[data-ua="Київська"]').click()
    pg.locator('#geoMap svg[data-ready="1"]').wait_for(state='attached', timeout=10000)
    assert pg.evaluate("document.querySelector('.route.is-sel').dataset.ua") == 'Київська'


def test_map_data_tool_is_green():
    r = subprocess.run([sys.executable, 'tools/geo_map.py'], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stdout + r.stderr
