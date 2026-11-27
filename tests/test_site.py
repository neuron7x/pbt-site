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


def test_brief_updates_the_existing_lead_without_network(page_factory):
    pg = page_factory(reduced=True)
    pending = []
    pg.on("request", lambda request: pending.append(request) if request.method == "POST" else None)
    assert pg.locator("#cTask").count() == 1
    pg.locator("#cTask").fill("Викопати траншею")
    pg.locator("#cPlace").fill("Полтава")
    pg.locator("#cOrder").click()
    assert pg.locator("#subject").input_value().startswith("Викопати траншею")
    assert pg.locator("#place").input_value() == "Полтава"
    assert not pending


def test_calculator_enter_does_not_navigate_or_execute_csp_blocked_handler(page_factory):
    """With hashed script CSP, Enter must never trigger a default GET form navigation."""
    pg = page_factory(reduced=True)
    assert pg.locator("#cTask").count() == 1
    before = pg.url
    pg.locator("#cTask").fill("Викопати траншею")
    pg.locator("#cTask").press("Enter")
    assert pg.locator("#subject").input_value().startswith("Викопати траншею")
    prevented = pg.evaluate("""() => {
      const event = new Event('submit', {bubbles: true, cancelable: true});
      document.getElementById('calcForm').dispatchEvent(event);
      return event.defaultPrevented;
    }""")
    assert prevented and pg.url.split('#')[0] == before.split('#')[0]
    assert not [e for e in pg.errors if "Refused to execute inline event handler" in e]


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
    assert pg.input_value('#subject').startswith('Плавучий екскаватор-амфібія')
    pg.fill('#hours', '16'); pg.fill('#km', '40'); pg.fill('#place', 'Полтава, Левада'); pg.fill('#name', 'Тест'); pg.fill('#contact', '097 863 77 77')
    pg.click('#send')
    pg.wait_for_selector('#done.is-on', timeout=5000)
    ref = pg.inner_text('#ref')
    assert re.fullmatch(r'№\s*\d{6}', ref)
    row = sqlite3.connect(server['db']).execute('select payload from leads order by id desc limit 1').fetchone()
    d = json.loads(row[0])
    assert d['type'] == 'rent' and d['hours'] == 16 and d['km'] == 40 and d['contact'] == '+380978637777'
    assert d['subject'].startswith('Плавучий екскаватор-амфібія')


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
    pg.wait_for_function('() => { const v = document.getElementById("heroVideo"); return v.currentSrc && v.currentSrc.includes("hero-wide") && v.readyState >= 2 && !v.paused; }', timeout=15000)
    assert pg.evaluate('document.querySelector("#hero").classList.contains("is-lit")')
    # Кожне слово короткого заголовка зберігає окрему анімацію появи.
    title = pg.locator('#heroTitle').inner_text().split()
    assert title and pg.locator('#heroTitle .w').count() == len(title)
    pg.evaluate('scrollTo({top: innerHeight * 1.1, behavior: "instant"})'); pg.wait_for_timeout(300)
    wl = float(pg.evaluate('getComputedStyle(document.getElementById("heroWater")).getPropertyValue("--wl")') or 0)
    assert 0 < wl < 1, wl
    pg.evaluate('scrollTo({top: innerHeight * 1.65, behavior: "instant"})'); pg.wait_for_timeout(300)
    wl2 = float(pg.evaluate('getComputedStyle(document.getElementById("heroWater")).getPropertyValue("--wl")'))
    assert wl2 > 0.9, wl2
    assert pg.evaluate('document.getElementById("heroVideo").paused') is True   # поза кадром відео не крутиться
    assert pg.evaluate('document.getElementById("gauge").classList.contains("is-on")')


@pytest.mark.parametrize('dpr,variant', [(1, 'hero-wide-720.'), (2, 'hero-wide.')])
def test_hero_rendition_follows_screen(page_factory, dpr, variant):
    """1440 css px × dpr 1 = 1440 фізичних < 1600 → легка 720; × dpr 2 = 2880 → 1920. Вантажимо те, що екран покаже."""
    pg = page_factory(dpr=dpr)
    pg.wait_for_function('() => document.getElementById("heroVideo").currentSrc', timeout=15000)
    assert variant in pg.evaluate('document.getElementById("heroVideo").currentSrc')


def test_mobile_hero_takes_portrait_cut(page_factory):
    pg = page_factory(390, 844, mobile=True)
    pg.wait_for_function('() => document.getElementById("heroVideo").currentSrc.includes("hero-tall")', timeout=15000)


def test_sections_reveal_and_counters_finish(page_factory):
    pg = page_factory()
    for sel in ('#roboty', '#jobs', '#dokaz', '#reel', '#geo', '#geoList'):
        pg.evaluate(f'document.querySelector("{sel}").scrollIntoView({{behavior: "instant", block: "center"}})'); pg.wait_for_timeout(450)
    pg.wait_for_timeout(1700)
    assert pg.evaluate('[...document.querySelectorAll("#roboty .rv, #dokaz .rv")].every(e => e.classList.contains("is-in"))')
    assert pg.evaluate('[...document.querySelectorAll("#roboty .rv")].every(e => getComputedStyle(e).opacity === "1")')
    nums = pg.evaluate('[...document.querySelectorAll("#dokaz [data-count]")].map(e => e.textContent)')
    assert nums == ['32', '9', '70 м'], nums
    assert pg.locator('#geoMap .route').count() == 8 and pg.locator('#geoMap .beacon').count() == 1   # 8 маршрутів з Полтави
    assert pg.locator('#reel .proof-card').count() == len(DATA['proof'])
    assert pg.locator('#dokaz img[src*="partners-"]').count() == 0


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
    pg.evaluate('document.getElementById("geo").scrollIntoView({behavior: "instant"})')
    pg.locator('#geoMap svg[data-ready="1"]').wait_for(state='attached')     # контури — ліниві дані (media/map/oblasts.json)
    assert pg.locator('#geoMap .obl').count() >= 25
    assert pg.locator('#geoMap .obl.served').count() == len(DATA['regions']) + 1   # + м. Київ як окремий контур у Київській
    assert pg.locator('#geoMap .obl.home').count() == 1


def test_404_page(page_factory):
    pg = page_factory(path='/nema-takoi-storinky')
    assert '404' in pg.inner_text('main') and 'Сторінки немає' in pg.title()


@pytest.mark.parametrize('w,h,mobile', VIEWPORTS[::2], ids=lambda v: str(v))
def test_axe_wcag22aa_zero_violations(page_factory, w, h, mobile):
    pg = page_factory(w, h, mobile=mobile, bypass_csp=True)
    pg.add_script_tag(path=str(ROOT / 'tests' / 'vendor' / 'axe.min.js'))
    # контраст міряємо в стані спокою: поява .rv (opacity/transform) посеред переходу давала хибні color-contrast
    # на .job:nth-child(5) у 3 з 6 прогонів навіть на main (07.10) — це гонка з анімацією, не дефект кольору
    pg.add_style_tag(content='*,*::before,*::after{transition:none!important;animation:none!important}')
    pg.evaluate("document.querySelectorAll('.rv').forEach(el => el.classList.add('is-in'))")
    pg.wait_for_timeout(50)
    res = pg.evaluate('axe.run(document, {runOnly: {type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]}})')
    bad = [(v['id'], v['impact'], [n['target'] for n in v['nodes']][:3]) for v in res['violations']]
    assert not bad, bad


GHOST_JS = """async (speed) => {
  const STEP = 1000 / 60, raf = () => new Promise(r => requestAnimationFrame(r));
  const els = [...document.querySelectorAll('.rv')].filter(e => !e.closest('#masshtab')), g = new Map(els.map(e => [e, 0]));
  const H = document.scrollingElement.scrollHeight - innerHeight; let t = 0;
  // крок віртуального часу — лише для анімацій на часовій шкалі документа; scroll-driven (view()) веде сам скрол
  const timed = () => document.getAnimations().filter(a => a.timeline instanceof DocumentTimeline);
  timed().forEach(a => a.pause());
  while (true) { t += STEP; const y = Math.min(H, t / 1000 * speed);
    scrollTo({top: y, behavior: 'instant'}); await raf(); await raf();          // IntersectionObserver доставлено
    timed().forEach(a => { a.pause(); a.currentTime = (a.currentTime || 0) + STEP; });
    for (const e of els) { if (e.hidden) continue; const b = e.getBoundingClientRect(); const vis = Math.min(b.bottom, innerHeight) - Math.max(b.top, 0);
      if (vis > Math.min(40, b.height / 2) && parseFloat(getComputedStyle(e).opacity) < 0.9) g.set(e, g.get(e) + STEP); }
    if (y >= H) break; }
  const v = [...g.values()].sort((a, b) => a - b);
  return {n: v.length, p50: Math.round(v[v.length >> 1]), p95: Math.round(v[Math.floor(v.length * .95)]), total: Math.round(v.reduce((a, b) => a + b, 0))}; }"""


@pytest.mark.parametrize('w,h,mobile', [(1440, 900, False), (390, 844, True)], ids=['desktop', 'phone'])
def test_reveal_does_not_ghost_content_on_normal_scroll(page_factory, w, h, mobile):
    """Поява секцій не має показувати напівпрозорий вміст на звичайному скролі (1200 px/с). «Примара» = блок помітно в кадрі з opacity < 0.9.
    Вимір у ВІРТУАЛЬНОМУ часі: скрол — кроками 1/60 с, CSS-переходи на паузі й просуваються на той самий крок (Web Animations API).
    Настінний варіант (до 09.10) накопичував реальну тривалість кадрів і червонів від чужого CI на машині (load 3–5 валив і main cee9963).
    Калібрування 09.10 (детерміновано, однакове при load 4.9): HEAD p95 150 / сума 5.9–6.4k;
    мутанти: старий rootMargin (.18, −8 %) 400–417 / 22–24k; старий перехід (0.9 с, повільний старт) 633 / 41k; обидва 883–900 / 55–59k."""
    pg = page_factory(w, h, mobile=mobile)
    r = pg.evaluate(GHOST_JS, 1200)
    assert r['n'] >= 60, r                                          # вимір справді пройшов по блоках, а не по порожньому списку
    assert r['p95'] < 250 and r['total'] < 12000, r


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


@pytest.mark.parametrize('theme', ['sky', 'precision'])
@pytest.mark.parametrize('w,h,mobile', [(1440, 900, False), (390, 844, True)], ids=['desktop', 'phone'])
def test_hero_lead_contrast_on_every_montage_frame(page_factory, w, h, mobile, theme):
    """Підзаголовок героя на монтажі, обидві теми. Раніше Sky давала 2.2:1 на білому MAN.
    10 точок монтажу, текст сховано, 90-й перцентиль яскравості фону під ним → ≥ 4.5:1."""
    import io
    from PIL import Image
    pg = page_factory(w, h, mobile=mobile)
    if theme == 'precision':
        pg.locator('[data-theme-choice="precision"]').click()
    pg.wait_for_timeout(1500)                                         # слова заголовка й підзаголовок з'являються по черзі
    fg = _lum([float(x) for x in re.findall(r'[\d.]+', pg.evaluate("getComputedStyle(document.querySelector('.hero__lead')).color"))[:3]])
    pg.add_style_tag(content='.hero__lead{color:transparent!important;text-shadow:none!important}')
    worst, seeks = [], []
    for k in range(10):
        ok = pg.evaluate(f"""async () => {{ const v = document.getElementById('heroVideo'), to = ms => new Promise(r => setTimeout(r, ms));
            if (v.readyState < 1) await Promise.race([new Promise(r => v.addEventListener('loadedmetadata', r, {{once: true}})), to(4000)]);
            v.pause(); v.currentTime = v.duration * {k} / 10 + 0.2;
            return await Promise.race([new Promise(r => v.addEventListener('seeked', () => r(1), {{once: true}})), to(3000).then(() => 0)]) }}""")
        seeks.append(ok)
        pg.wait_for_timeout(250)
        im = Image.open(io.BytesIO(pg.screenshot(clip=pg.locator('.hero__lead').bounding_box()))).convert('RGB').resize((80, 16))
        ls = sorted(_lum(px) for px in im.get_flattened_data()); bg = ls[int(len(ls) * .9)]
        worst.append(round((max(fg, bg) + .05) / (min(fg, bg) + .05), 2))
    assert sum(seeks) == 10, f'seeked прийшов {sum(seeks)}/10 — вимір не по різних кадрах'   # сетер currentTime повертає записане й без seek
    assert len(set(worst)) >= 5, worst                              # різні кадри → різний фон
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


CHIPS_JS = """() => { const c = document.getElementById('chips'), cb = c.getBoundingClientRect(), ch = [...c.querySelectorAll('.chip')], rows = {};
  ch.forEach(x => { const t = Math.round(x.getBoundingClientRect().top); rows[t] = (rows[t] || 0) + 1 });
  return {rows: Object.values(rows), clipped: ch.filter(x => { const b = x.getBoundingClientRect(); return b.left < cb.left - .5 || b.right > cb.right + .5 }).length,
          scroll: c.scrollWidth > c.clientWidth + 1, mask: getComputedStyle(c).maskImage !== 'none' || (getComputedStyle(c).webkitMaskImage || 'none') !== 'none'} }"""


@pytest.mark.parametrize('w', [1920, 1440, 1024, 820])
def test_fleet_filters_all_visible_and_balanced(page_factory, w):
    """Було: прихована прокрутка без підказки — обрізаний останній фільтр на 1440, 4 з 9 на 820. Тепер ≥ 820 px: усі видно, 5 + 4."""
    r = page_factory(w, 900).evaluate(CHIPS_JS)
    assert r['clipped'] == 0 and r['rows'] == [5, 4], r


@pytest.mark.parametrize('w', [819, 390])
def test_fleet_filters_scroll_with_edge_fade_on_narrow(page_factory, w):
    """< 820 px фільтри прокручуються — край має затухати, щоб було видно, що є ще."""
    r = page_factory(w, 900, mobile=w < 700).evaluate(CHIPS_JS)
    assert r['scroll'] and r['mask'] and r['rows'] == [9], r


def test_keyboard_focus_brings_filter_into_view_on_phone(page_factory):
    """Аудит a5951a5: Tab до останнього фільтра на 390 px лишав його на 107 px за краєм (і в зоні затухання маски)."""
    pg = page_factory(390, 844, mobile=True)
    pg.evaluate("document.getElementById('chips').scrollIntoView({block: 'center', behavior: 'instant'})")
    pg.focus('#chips .chip:first-child')
    for _ in range(8):
        pg.keyboard.press('Tab')
    pg.wait_for_timeout(700)                                          # плавна прокрутка до фокуса
    r = pg.evaluate("""() => { const a = document.activeElement, b = a.getBoundingClientRect(); return {cat: a.dataset.cat, l: b.left, r: b.right, w: innerWidth} }""")
    assert r['cat'] == 'trans', r                                   # останній фільтр
    assert r['l'] >= 18 and r['r'] <= r['w'] - 42, r                # поза зонами затухання маски (18 / 42 px)


def test_material_photos_sharp_on_retina_phone(page_factory):
    """Телефон dpr 3: картка матеріалу ≈350 css px = 1050 фізичних > 639 оригіналу ⇒ має прийти @2x (1278 px)."""
    pg = page_factory(390, 844, mobile=True, dpr=3)
    pg.evaluate('document.getElementById("materialy").scrollIntoView()')
    pg.wait_for_function('() => [...document.querySelectorAll("#materialy img")].some(i => i.complete && i.naturalWidth)', timeout=10000)
    imgs = pg.evaluate('[...document.querySelectorAll("#materialy img")].filter(i => i.currentSrc).map(i => i.currentSrc)')
    assert imgs and all('@2x.webp' in s for s in imgs), imgs   # naturalWidth тут у css px (1278/2), тому міряємо джерело
    from PIL import Image
    assert Image.open(ROOT / 'web' / 'media' / 'mat' / 'mat-1@2x.webp').size == (1278, 792)


def test_hero_autoplays_in_webkit(pw, server):
    """Safari (WebKit) мовчки ігнорує play(), викликаний одразу після підстановки <source>; Chromium — ні.
    08.10: у WebKit герой стояв на паузі (currentTime 0 через 4 с), картки й «Масштаб» грали — їм play() кличе IntersectionObserver пізніше."""
    try:
        b = pw.webkit.launch()
    except Exception as e:                                   # рушій не встановлено — це «не запускалось», не «пройшло»
        pytest.skip(f'webkit недоступний: {e}')
    try:
        pg = b.new_page(viewport={'width': 1440, 'height': 900})
        pg.goto(server['base'] + '/')
        pg.wait_for_function('() => { const v = document.getElementById("heroVideo"); return v && !v.paused && v.currentTime > 0.5; }', timeout=8000)
    finally:
        b.close()


def test_brand_logo_animates_once_then_rests(page_factory):
    """Логотип власника (tools/logo.py): статичний кадр одразу (LCP), VP9-анімація з альфою грає раз і віддає місце статичному."""
    pg = page_factory(init_script="""
      new MutationObserver(records => {
        if (records.some(record => record.target.matches('.logo-hero.is-anim'))) {
          window.pbtLogoWasAnimated = true;
        }
      }).observe(document, {subtree: true, attributes: true, attributeFilter: ['class']});
    """)
    assert pg.evaluate('document.querySelector(".logo-hero__img").complete && document.querySelector(".logo-hero__img").naturalWidth') == 960
    pg.wait_for_function('() => window.pbtLogoWasAnimated === true', timeout=8000)
    pg.wait_for_function('() => document.getElementById("logoAnim").ended && !document.querySelector(".logo-hero").classList.contains("is-anim")', timeout=12000)
    assert pg.evaluate('document.querySelectorAll(".brand__logo").length') == 2           # шапка й підвал


def test_brand_logo_static_in_webkit(pw, server):
    """Safari не показує альфу VP9 (замість прозорості — чорне тло) ⇒ у WebKit анімація не підставляється, лишається статичний кадр."""
    try:
        b = pw.webkit.launch()
    except Exception as e:
        pytest.skip(f'webkit недоступний: {e}')
    try:
        pg = b.new_page(viewport={'width': 1440, 'height': 900}); pg.goto(server['base'] + '/'); pg.wait_for_timeout(3000)
        assert pg.evaluate('document.getElementById("logoAnim").currentSrc') == ''
        assert pg.evaluate('document.querySelector(".logo-hero__img").naturalWidth') == 960
    finally:
        b.close()


def test_copy_typography_is_normalized(page_factory):
    """Коректура 09.10: дані пройшли tools/copyedit.py; у видимому тексті — апостроф ’, нерозривний пробіл між числом і одиницею,
    звернення на «ви», жодних ієрогліфів (CJK) — ні в тексті, ні в атрибутах."""
    import subprocess, sys
    r = subprocess.run([sys.executable, str(ROOT / 'tools' / 'copyedit.py'), '--check'], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
    pg = page_factory()
    pg.evaluate('(async () => { for (let y = 0; y < document.body.scrollHeight; y += 700) { scrollTo(0, y); await new Promise(r => setTimeout(r, 30)); } })()')
    pg.wait_for_timeout(1500)
    t = pg.evaluate("document.body.innerText + ' ' + [...document.querySelectorAll('[alt],[placeholder],[aria-label]')].map(e => (e.alt || '') + ' ' + (e.placeholder || '') + ' ' + (e.getAttribute('aria-label') || '')).join(' ')")
    assert not re.findall(r"[А-ЯІЇЄҐа-яіїєґ]'[А-ЯІЇЄҐа-яіїєґ]", t), 'ASCII-апостроф у тексті'
    glued = re.findall(r'\d(?:т|л|м|км|грн)\b', t)
    assert not glued, glued
    assert not re.findall(r'[⺀-鿿가-힯]', t), 'ієрогліфи на сторінці'
    assert not re.findall(r'\b(?:Обери|Заповни|натисни|подзвони|Гортай|Вкажи|Перевір|до тебе)\b', t, re.I), 'звернення на «ти»'


@pytest.mark.parametrize('w,h,mobile', [(1366, 650, False), (1280, 600, False), (1920, 700, False), (1024, 768, False), (360, 640, True), (390, 664, True)],
                         ids=lambda v: str(v))
def test_hero_content_fits_between_nav_and_bottom(page_factory, w, h, mobile):
    """09.10, скрін власника: на 1366×650 підзаголовок «Полтава · 9 областей · 24/7» заїжджав під меню — тексти накладались
    у «ієрогліфи». Вміст героя має стояти нижче шапки й вище низу екрана (або підказки «Гортайте», якщо вона видима);
    цифри — в один ряд."""
    pg = page_factory(w, h, mobile=mobile)
    pg.wait_for_timeout(1500)
    r = pg.evaluate("""(() => { const g = s => document.querySelector(s).getBoundingClientRect(), hint = document.querySelector('.hero__hint');
      const hv = getComputedStyle(hint).display !== 'none', st = [...document.querySelectorAll('.hero__stats li')].map(li => Math.round(li.getBoundingClientRect().top));
      return {nav: g('#nav').bottom, top: g('#heroCenter .eyebrow').top, bottom: g('.hero__stats').bottom, limit: hv ? g('.hero__hint').top : innerHeight - 6, rows: new Set(st).size}; })()""")
    assert r['top'] >= r['nav'] + 6 and r['bottom'] <= r['limit'] - 6, r
    assert r['rows'] == 1, r
