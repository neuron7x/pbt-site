"""Спокій периферії (аудит 24.11, п.50). Периферія сітківки найчутливіша до руху: кожен вічний цикл — екзогенне
захоплення уваги, що конкурує з читанням ціни й заповненням форми.

Інваріанти: (б) маяки dip/ring/home — ≤ 3 повтори; (г) цикл поза в'юпортом на паузі; (в) фокус у полі форми —
жоден декоративний цикл не біжить; (д) жоден цикл не модулює в смузі 3–30 Гц (WCAG 2.3.1): період ≥ 1/3 с.
"""
import pytest

LOOPS = """() => document.getAnimations().filter(a => a.effect && a.effect.getTiming).map(a => {
  const t = a.effect.getTiming(), el = a.effect.target, r = el.getBoundingClientRect();
  return {name: a.animationName || '', iters: t.iterations, dur: Number(t.duration) || 0, state: a.playState,
          inView: r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth && r.width * r.height > 0,
          sel: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + '.' + [...el.classList].join('.')}; })"""


def _settle(pg, js):
    pg.evaluate(js)
    pg.wait_for_timeout(700)


def _visit_all(pg):
    pg.evaluate("document.getElementById('geo').scrollIntoView({behavior:'instant'})")
    pg.locator('#geoMap svg[data-ready="1"]').wait_for(state='attached')
    pg.wait_for_timeout(500)


def test_beacons_are_finite_and_no_flicker_band(page_factory):
    pg = page_factory(1440, 900)
    seen = pg.evaluate(LOOPS)
    _visit_all(pg)
    seen += pg.evaluate(LOOPS)
    names = {a['name'] for a in seen}
    assert {'dip', 'ring', 'home'} <= names, names
    for a in seen:
        if a['name'] in ('dip', 'ring', 'home'):
            assert a['iters'] <= 3, a
        if a['iters'] == float('inf') or a['iters'] is None:
            assert a['dur'] >= 1000 / 3, a                          # повний цикл ≥ 333 мс: поза 3–30 Гц


@pytest.mark.parametrize('where', ['tekhnika', 'zapyt'])
def test_loops_off_screen_are_paused(page_factory, where):
    pg = page_factory(1440, 900)
    _visit_all(pg)
    _settle(pg, f"document.getElementById('{where}').scrollIntoView({{behavior:'instant'}})")
    running = [a for a in pg.evaluate(LOOPS) if a['state'] == 'running' and not a['inView']
               and (a['iters'] == float('inf') or a['iters'] is None or a['iters'] > 1)]
    assert not running, running


def test_form_focus_freezes_decorative_loops(page_factory):
    pg = page_factory(1440, 900)
    _visit_all(pg)
    pg.locator('#lead input:not([type=hidden])').first.focus()
    pg.wait_for_timeout(200)
    running = [a for a in pg.evaluate(LOOPS) if a['state'] == 'running'
               and (a['iters'] == float('inf') or a['iters'] is None or a['iters'] > 1)]
    assert not running, running
