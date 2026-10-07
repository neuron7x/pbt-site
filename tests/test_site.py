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
    pg.wait_for_function(f'() => document.getElementById("cTotal").textContent.replace(/\\D/g, "") === "{expected}"', timeout=4000)   # сума дотвінюється за 520 мс
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


def test_hero_video_plays_and_scene_dives(page_factory):
    pg = page_factory()
    assert pg.get_attribute('#heroVideo', 'poster').endswith('hero-wide.webp')
    pg.wait_for_function('(() => { const v = document.getElementById("heroVideo"); return v.currentSrc && v.currentSrc.includes("hero-wide") && v.readyState >= 2 && !v.paused; })()', timeout=15000)
    assert pg.evaluate('document.querySelector("#hero").classList.contains("is-lit")')
    assert pg.locator('#heroTitle .w').count() >= 6                       # слова заголовка — окремі спани появи
    pg.evaluate('scrollTo({top: innerHeight * 1.1, behavior: "instant"})'); pg.wait_for_timeout(300)
    wl = float(pg.evaluate('getComputedStyle(document.getElementById("heroWater")).getPropertyValue("--wl")') or 0)
    assert 0 < wl < 1, wl
    pg.evaluate('scrollTo({top: innerHeight * 1.65, behavior: "instant"})'); pg.wait_for_timeout(300)
    wl2 = float(pg.evaluate('getComputedStyle(document.getElementById("heroWater")).getPropertyValue("--wl")'))
    assert wl2 > 0.9, wl2
    assert pg.evaluate('document.getElementById("heroVideo").paused') is True   # поза кадром відео не крутиться
    assert pg.evaluate('document.getElementById("gauge").classList.contains("is-on")')


def test_mobile_hero_takes_portrait_cut(page_factory):
    pg = page_factory(390, 844, mobile=True)
    pg.wait_for_function('() => document.getElementById("heroVideo").currentSrc.includes("hero-tall")', timeout=15000)


def test_sections_reveal_and_counters_finish(page_factory):
    pg = page_factory()
    for sel in ('#roboty', '#jobs', '#dokaz', '#reel', '#partners', '#geo', '#geoList'):
        pg.evaluate(f'document.querySelector("{sel}").scrollIntoView({{behavior: "instant", block: "center"}})'); pg.wait_for_timeout(450)
    pg.wait_for_timeout(1700)
    assert pg.evaluate('[...document.querySelectorAll("#roboty .rv, #dokaz .rv")].every(e => e.classList.contains("is-in"))')
    assert pg.evaluate('[...document.querySelectorAll("#roboty .rv")].every(e => getComputedStyle(e).opacity === "1")')
    nums = pg.evaluate('[...document.querySelectorAll("#dokaz [data-count]")].map(e => e.textContent)')
    assert nums == ['32', '9', '70 м'], nums
    assert pg.locator('#geoMap .route').count() == 8 and pg.locator('#geoMap .beacon').count() == 1   # 8 маршрутів з Полтави
    assert pg.evaluate('document.getElementById("partners").children.length') == len(DATA['partners']) * 2  # стрічка подвоєна


def test_job_and_proof_videos_play_in_view(page_factory, server):
    import urllib.request
    pg = page_factory()
    pg.evaluate('document.querySelector("#jobs").scrollIntoView({behavior: "instant", block: "center"})')
    pg.wait_for_function('() => document.querySelectorAll("#jobs .job.is-playing").length >= 3', timeout=15000)
    pg.evaluate('document.querySelector("#reel").scrollIntoView({behavior: "instant", block: "center"})')
    pg.wait_for_function('() => document.querySelectorAll("#reel a.is-playing").length >= 3', timeout=15000)
    assert pg.locator('#reel a').count() == len(DATA['proof']) == 6
    for name in ['hero-wide', 'hero-tall'] + [j['video'] for j in DATA['jobs']] + [p['video'] for p in DATA['proof']]:
        for ext in ('mp4', 'webm', 'webp'):
            r = urllib.request.urlopen(server['base'] + f'/media/video/{name}.{ext}')
            assert r.status == 200 and int(r.headers['Content-Length']) > 5000, (name, ext)


def test_reduced_motion_is_static_but_complete(page_factory):
    pg = page_factory(reduced=True)
    assert pg.evaluate('document.documentElement.dataset.quality') == 'static'
    assert pg.evaluate('!document.getElementById("heroVideo").currentSrc')          # без руху — лише постер
    assert pg.locator('h1').is_visible() and pg.locator('#park .unit').count() == 32
    assert pg.evaluate('[...document.querySelectorAll(".rv")].every(e => getComputedStyle(e).opacity === "1")')   # усе видно одразу


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
    # контраст міряємо в стані спокою: поява .rv (opacity/transform) посеред переходу давала хибні color-contrast
    # на .job:nth-child(5) у 3 з 6 прогонів навіть на main (07.10) — це гонка з анімацією, не дефект кольору
    pg.add_style_tag(content='*,*::before,*::after{transition:none!important;animation:none!important}')
    pg.evaluate("document.querySelectorAll('.rv').forEach(el => el.classList.add('is-in'))")
    pg.wait_for_timeout(50)
    res = pg.evaluate('axe.run(document, {runOnly: {type: "tag", values: ["wcag2a", "wcag2aa", "wcag22aa"]}})')
    bad = [(v['id'], v['impact'], [n['target'] for n in v['nodes']][:3]) for v in res['violations'] if v['impact'] in ('serious', 'critical')]
    assert not bad, bad


GHOST_JS = """async (speed) => {
  const els = [...document.querySelectorAll('.rv')].filter(e => !e.closest('#masshtab')), g = new Map(els.map(e => [e, 0]));
  const H = document.scrollingElement.scrollHeight - innerHeight; const t0 = performance.now(); let last = t0;
  while (true) { const now = performance.now(), dt = now - last; last = now; const y = Math.min(H, (now - t0) / 1000 * speed);
    scrollTo({top: y, behavior: 'instant'}); await new Promise(r => requestAnimationFrame(r));
    for (const e of els) { if (e.hidden) continue; const b = e.getBoundingClientRect(); const vis = Math.min(b.bottom, innerHeight) - Math.max(b.top, 0);
      if (vis > Math.min(40, b.height / 2) && parseFloat(getComputedStyle(e).opacity) < 0.9) g.set(e, g.get(e) + dt); }
    if (y >= H) break; }
  const v = [...g.values()].sort((a, b) => a - b);
  return {n: v.length, p50: v[v.length >> 1], p95: v[Math.floor(v.length * .95)], total: v.reduce((a, b) => a + b, 0)}; }"""


@pytest.mark.parametrize('w,h,mobile', [(1440, 900, False), (390, 844, True)], ids=['desktop', 'phone'])
def test_reveal_does_not_ghost_content_on_normal_scroll(page_factory, w, h, mobile):
    """Поява секцій не має показувати напівпрозорий вміст на звичайному скролі (1200 px/с, `behavior: instant` —
    `scroll-behavior: smooth` інакше гасить сам скрол). «Примара» = блок помітно в кадрі з opacity < 0.9.
    Було (threshold .18, −8 %, 0.9 с з повільним стартом): p50 801 мс, p95 1029 мс, разом 61 с на сторінку. Стало ≈ 157 / 215 мс."""
    pg = page_factory(w, h, mobile=mobile)
    r = pg.evaluate(GHOST_JS, 1200)
    assert r['n'] >= 60, r                                          # вимір справді пройшов по блоках, а не по порожньому списку
    assert r['p95'] < 400 and r['total'] < 20000, r


@pytest.mark.parametrize('w,h,mobile', [(1440, 900, False), (390, 844, True)], ids=['desktop', 'phone'])
def test_hero_video_covers_hero_edge_to_edge(page_factory, w, h, mobile):
    """`img,video{max-width:100%}` різав .hero__video (inset −2 %, width 104 %) до 100 % → праворуч смуга 2 % без відео (29 px на 1440)."""
    pg = page_factory(w, h, mobile=mobile)
    v, hero = pg.evaluate("""() => ['#heroVideo', '#hero'].map(s => { const b = document.querySelector(s).getBoundingClientRect(); return [b.left, b.right] })""")
    assert v[0] <= hero[0] and v[1] >= hero[1], (v, hero)


def _lum(px):
    lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(v / 255) for v in px[:3])
    return .2126 * r + .7152 * g + .0722 * b


@pytest.mark.parametrize('w,h,mobile', [(1440, 900, False), (390, 844, True)], ids=['desktop', 'phone'])
def test_hero_lead_contrast_on_every_montage_frame(page_factory, w, h, mobile):
    """Підзаголовок героя (#EAF6FF, 15–18 px) лежить на монтажі. Було 2.2:1 на кадрі з білим MAN (4 з 10 кадрів < 4.5).
    10 точок монтажу, текст сховано, 90-й перцентиль яскравості фону під ним → ≥ 4.5:1."""
    import io
    from PIL import Image
    pg = page_factory(w, h, mobile=mobile)
    pg.wait_for_timeout(1500)                                         # слова заголовка й підзаголовок з'являються по черзі
    fg = _lum([float(x) for x in re.findall(r'[\d.]+', pg.evaluate("getComputedStyle(document.querySelector('.hero__lead')).color"))[:3]])
    pg.add_style_tag(content='.hero__lead{color:transparent!important;text-shadow:none!important}')
    worst = []
    for k in range(10):
        pg.evaluate(f"""async () => {{ const v = document.getElementById('heroVideo'), to = ms => new Promise(r => setTimeout(r, ms));
            if (v.readyState < 1) await Promise.race([new Promise(r => v.addEventListener('loadedmetadata', r, {{once: true}})), to(4000)]);
            v.pause(); v.currentTime = v.duration * {k} / 10 + 0.2;
            await Promise.race([new Promise(r => v.addEventListener('seeked', r, {{once: true}})), to(3000)]) }}""")
        pg.wait_for_timeout(250)
        im = Image.open(io.BytesIO(pg.screenshot(clip=pg.locator('.hero__lead').bounding_box()))).convert('RGB').resize((80, 16))
        ls = sorted(_lum(px) for px in im.getdata()); bg = ls[int(len(ls) * .9)]
        worst.append(round((max(fg, bg) + .05) / (min(fg, bg) + .05), 2))
    assert pg.evaluate("document.getElementById('heroVideo').currentTime") > 0, 'seek не спрацював — вимір по одному кадру'
    assert min(worst) >= 4.5, worst


@pytest.mark.parametrize('w', [320, 390])
def test_eyebrows_stay_on_one_line_on_phones(page_factory, w):
    """Було: на 390 px «Полтава · 9 областей · 24/7» переносилось («24/7» окремим рядком), на 320 — і «Орієнтовна вартість»."""
    pg = page_factory(w, 800, mobile=True)
    r = pg.evaluate("""() => [...document.querySelectorAll('.eyebrow')].filter(e => e.offsetParent).map(e => {
        const b = e.getBoundingClientRect(), fs = parseFloat(getComputedStyle(e).fontSize);
        return {t: e.textContent.trim(), lines: Math.round(b.height / fs), inside: b.left >= -0.5 && b.right <= innerWidth + 0.5} })""")
    assert len(r) >= 8, r
    bad = [x for x in r if x['lines'] > 1 or not x['inside']]
    assert not bad, bad
