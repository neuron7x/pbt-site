"""А3-core, крок 2: декоративні цикли сторінки ділять один запит кадру (web/js/clock.js).

До цього кроку іскри героя, гусениця, масло й курсорне світло кожен просили власний кадр: під час прокрутки героя з
рухом миші сторінка ставила до п'яти requestAnimationFrame на кадр. Тепер — один на всі цикли плюс один на обробку
прокрутки. Лічимо справжні виклики requestAnimationFrame за кадр, поки всі чотири цикли живі.
"""
COUNTER = """
(() => {
  const real = window.requestAnimationFrame.bind(window);
  const log = { frames: [], cur: 0, on: false };
  window.__raf = log;
  window.requestAnimationFrame = cb => { if (log.on) log.cur++; return real(cb); };
  const mark = () => { if (log.on) { log.frames.push(log.cur); log.cur = 0; } real(mark); };   // межа кадру; сам лічильник не рахується
  real(mark);
})();
"""


def _drive(pg, seconds=1.6):
    """Прокрутка в межах героя (іскри, гусениця, масло) з рухом миші (курсорне світло)."""
    pg.evaluate("window.__raf.cur = 0; window.__raf.frames = []; window.__raf.on = true")
    steps = int(seconds / 0.04)
    for i in range(steps):
        pg.mouse.wheel(0, 34 if (i // 12) % 2 == 0 else -34)
        pg.mouse.move(300 + (i * 23) % 700, 240 + (i * 17) % 300)
        pg.wait_for_timeout(40)
    pg.evaluate("window.__raf.on = false")
    return pg.evaluate("window.__raf.frames")


def test_decorative_loops_share_one_frame_request(browser, server):
    ctx = browser.new_context(viewport={'width': 1440, 'height': 900})
    try:
        ctx.add_init_script("Object.defineProperty(navigator, 'hardwareConcurrency', {configurable: true, value: 8});")
        ctx.add_init_script(COUNTER)
        pg = ctx.new_page()
        errors = []
        pg.on('pageerror', lambda e: errors.append(str(e)))
        pg.goto(server['base'] + '/', wait_until='networkidle')
        assert pg.evaluate("document.documentElement.dataset.quality") == 'full'
        # без планувальника це має бути збій твердження, а не виняток браузера (tools/red_on_base.py зараховує лише твердження)
        assert pg.evaluate("typeof (window.PBTClock && window.PBTClock.createClock)") == 'function'
        pg.wait_for_timeout(2600)                                   # поява героя й лічильники чисел завершились
        before = pg.evaluate("""({tx: getComputedStyle(document.getElementById('track')).getPropertyValue('--tx'),
                                  glow: document.getElementById('glow').style.transform})""")
        frames = _drive(pg)
        after = pg.evaluate("""({tx: getComputedStyle(document.getElementById('track')).getPropertyValue('--tx'),
                                 glow: document.getElementById('glow').style.transform,
                                 y: scrollY, hero: document.querySelector('.s-hero').offsetHeight})""")
        assert not errors, errors
        assert len(frames) >= 40, len(frames)                       # виміряно достатньо кадрів
        # цикли справді працювали: ланцюг зсунувся, світло пішло за курсором, герой лишався в кадрі (іскри живі)
        assert after['tx'] != before['tx'] and after['glow'] != before['glow'], (before, after)
        assert after['y'] < after['hero'], after
        busy = [n for n in frames if n > 0]
        assert len(busy) >= 30, len(busy)
        # один запит на всі декоративні цикли + один на обробку прокрутки
        assert max(frames) <= 2, sorted(frames)[-6:]
    finally:
        ctx.close()


def test_page_never_asks_for_frames_when_nothing_moves(browser, server):
    """Спокій: без прокрутки й миші поза героєм сторінка не просить кадрів — планувальник не крутиться вхолосту."""
    ctx = browser.new_context(viewport={'width': 1440, 'height': 900})
    try:
        ctx.add_init_script(COUNTER)
        pg = ctx.new_page()
        pg.goto(server['base'] + '/', wait_until='networkidle')
        pg.evaluate("document.getElementById('cina').scrollIntoView({behavior: 'instant', block: 'start'})")
        pg.wait_for_timeout(3000)                                   # гусениця догнала сторінку, масло стекло
        pg.evaluate("window.__raf.cur = 0; window.__raf.frames = []; window.__raf.on = true")
        pg.wait_for_timeout(800)
        frames = pg.evaluate("(window.__raf.on = false, window.__raf.frames)")
        assert len(frames) >= 20 and sum(frames) == 0, sorted(frames)[-6:]
    finally:
        ctx.close()
