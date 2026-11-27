#!/usr/bin/env python3
"""Кран-глибиномір теми «Сталь»: канат, гакова підвіска, вантаж і його кадри — згенеровано, а не вставлено руками.

Вся графіка — власна, намальована тут: SVG у data-URI всередині web/css/site.css (CSP: img-src data:), без файлів і запитів.
Будівельник — оригінальний векторний персонаж у палітрі бренду; чужих спрайтів і торгових марок немає (docs/PROVENANCE.md).

Кадр 16×44 клітинки, клітинка 2 px (постать 32×44 px):
  0–11   будівельник махає руками, падають монети
  12     будівельник стоїть унизу
  13     знаки долара на землі після падіння
  14–37  смарагдовий каскад під гаком
  38     знаки долара на нерухомому гаку
  39     будівельник висить на гаку

  python3 tools/crane.py            — розміри й кількість кадрів
  python3 tools/crane.py --write    — вписати блок між маркерами у web/css/site.css
  python3 tools/crane.py --check    — вихід 1, якщо блок у CSS не відповідає цьому файлу
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / 'web' / 'css' / 'site.css'
BEGIN, END = '/* crane:begin — згенеровано tools/crane.py, руками не правити */', '/* crane:end */'
P = ':is(:root[data-theme="sky"],:root:not([data-theme]))'
CELL, FW, BODY, FH = 2, 16, 22, 44                       # px на клітинку; кадр 16×44 клітинки: 22 — постать, 22 — простір падіння частинок
PAL = {'Y': '#FDC501', 'y': '#C99700', 'H': '#FFE98A', 'B': '#1238A8'}
# Власний рисунок у координатах видимого кадру 32×44 px. Тіні на тканині,
# металеві пряжки й світловідбивні смуги залишаються читабельними при масштабі 0,62.
WORKER_PAINT = f"""
<linearGradient id='helmet' x2='.85' y2='1'><stop stop-color='#FFF0A8'/><stop offset='.46' stop-color='{PAL['Y']}'/><stop offset='1' stop-color='#A9610A'/></linearGradient>
<linearGradient id='face' x2='.82' y2='.85'><stop stop-color='#FAD3AB'/><stop offset='.57' stop-color='#CE936B'/><stop offset='1' stop-color='#754932'/></linearGradient>
<linearGradient id='vest' x2='1' y2='.75'><stop stop-color='#FFB257'/><stop offset='.52' stop-color='#E87929'/><stop offset='1' stop-color='#9F4219'/></linearGradient>
<linearGradient id='workwear' x2='1' y2='.15'><stop stop-color='#64768C'/><stop offset='.48' stop-color='{PAL['B']}'/><stop offset='1' stop-color='#142235'/></linearGradient>
"""

WORKER_UPPER = """
<path d='M13.1 15.1h5.5l.5 3.5H12.6z' fill='url(#face)'/>
<path d='M10.8 19l2.6-1.8 2.6 1.9 2.8-2 3.6 2 1.2 9.7-2 2.6-10.5-.1-2.2-2z' fill='url(#vest)' stroke='#5D3B29' stroke-width='.55'/>
<path d='M14 17.7l2 1.4 2-1.4-.6 4.1-1.4 2-1.2-2z' fill='#304256'/>
<path d='M11.5 19.2l1.2 9.3m8.2-9.2l-.8 9.2M10.4 27.4l12.4.1' fill='none' stroke='#E3E7E0' stroke-width='1.05'/>
<path d='M16 23.3l.2 6.5m2.5-6.7h2.4m-10 2.7h2.4' fill='none' stroke='#7D411F' stroke-width='.5'/>
<path d='M12 10.2l7.9-.2.1 2.4-.7 2.9-1.6 1.5-2.6.2-2.4-1.5-1-2.8z' fill='url(#face)' stroke='#6D472F' stroke-width='.45'/>
<path d='M13.5 12.5h.7m3.6-.1h.8m-4.5 2.7l1.9-.6 1.9.5' fill='none' stroke='#432D26' stroke-width='.65' stroke-linecap='round'/>
<path d='M11.2 10a5 5 0 0 1 9.9-.1l1.4.6-.1.8-12.8.1-.2-.7z' fill='url(#helmet)' stroke='#694717' stroke-width='.5'/>
<path d='M12 9.3a4.5 4.5 0 0 1 3.2-2.8m1.2-.3 1 3.8' fill='none' stroke='#FFF1AB' stroke-width='.55' stroke-linecap='round'/>
"""

FEET_DOWN = """
<path d='M10.8 30.2l10.6.1.7 5.1.2 5.4-3.7.2-1.8-6.6-.8-.1-1.9 6.9-3.7-.2.1-6.2z' fill='url(#workwear)' stroke='#192536' stroke-width='.65'/>
<path d='M11 40.1h3.6l.1 2.4-.9.9-5.4-.1.1-1.2zm7.4.1 3.6-.2 2 1.8.1 1.4-5.6.1-.5-.8z' fill='#252B2F' stroke='#101820' stroke-width='.4'/>
<path d='M11.5 35.1l-.3 3.7m9.6-3.4.5 3.5' stroke='#899AB2' stroke-opacity='.7' stroke-width='.6'/>
"""

FEET_HANG = """
<path d='M10.8 30.2l10.6.1.8 5.2-1.2 5.4-3.5-.2.5-5.7-1.9-.8-1.6 2-.5 5.4-3.7-.2.3-6.2z' fill='url(#workwear)' stroke='#192536' stroke-width='.65'/>
<path d='M10.2 40.6l3.9.2-.1 2.1-3 1-2.3-.5.4-1.3zm7.2-.7 3.6.1 1.5 1.7-.1 1.3-2.2.2-3.1-.7z' fill='#252B2F' stroke='#101820' stroke-width='.4'/>
<path d='M12 34.6l-.5 4.5m9.3-4-.7 3.2' stroke='#899AB2' stroke-opacity='.7' stroke-width='.6'/>
"""

LEFT_DOWN = """<path d='M11.3 18.9l-2.9.5-2 3.5-.7 6.8 2.5.6 1.4-5.8 1.6-2.4z' fill='url(#workwear)' stroke='#192536' stroke-width='.55'/>
<path d='M5.9 29.1l2.5.5-.2 2.4-.8 1-1.4-.5-.4-1.5z' fill='#56626A' stroke='#27353E' stroke-width='.42'/>"""
LEFT_WAVE = """<path d='M11.2 19.4l-2 .3-2.9-1.8-.7-6-2.9.2.2 7.2 4.2 4.1 3.9-.9z' fill='url(#workwear)' stroke='#192536' stroke-width='.55'/>
<path d='M2.9 12.5l-.8-2.2.4-2.8.6-.3.3 1.9.6-2 .7.1.4 2.4.7-.6.6.3-.8 3.1z' fill='#68757B' stroke='#27353E' stroke-width='.42'/>"""
LEFT_REACH = """<path d='M11.3 19l-2.3-.2-3.8 3.1-3.1-2.4-1.4 2.1 4.5 3.5 5.5-2.5z' fill='url(#workwear)' stroke='#192536' stroke-width='.55'/>
<path d='M2.3 19.6l-.3-1.4-1.3-.9-.5.5.7 1.1-.5.8.4 1.8z' fill='#68757B' stroke='#27353E' stroke-width='.42'/>"""
LEFT_FLICK = """<path d='M11.2 19.4l-2 .3-2.6-3.3 1.1-5.8-2.7-.6-1.4 7.1 3.5 6.3 3.9-.9z' fill='url(#workwear)' stroke='#192536' stroke-width='.55'/>
<path d='M5.1 10.6l-.5-1.8L6 6.3l.6.1-.2 1.8 1.1-1.6.6.3-.6 2.1.9-.2.4.5-1.5 2.2z' fill='#68757B' stroke='#27353E' stroke-width='.42'/>"""
RIGHT_ARM = """<path d='M21.8 19l2.8.7 1.9 4.4 1 5.3-2.7.7-1.5-5.3-1.7-2.7z' fill='url(#workwear)' stroke='#192536' stroke-width='.55'/>
<path d='M24.9 29.2l2.5-.5.8 2.1-.5 1.7-1.4.4-1-.8z' fill='#56626A' stroke='#27353E' stroke-width='.42'/>"""

LANYARD = """
<path d='M15.8 4.6L10 19.2m6-14.6 6 14.6' stroke='#26343E' stroke-width='1.65' stroke-linecap='round'/>
<path d='M15.8 4.6L10 19.2m6-14.6 6 14.6' stroke='#C2CDD2' stroke-width='.65' stroke-linecap='round'/>
<ellipse cx='15.9' cy='3.2' rx='1.35' ry='2' fill='none' stroke='#D9E2E6' stroke-width='1.05'/>
"""
HARNESS = """
<path d='M10.3 18.9l3.8 8.2-2.8 3.7m10.2-11.9-3.8 8.2 2.9 3.7m-6.5-3.7h3.6' fill='none' stroke='#303840' stroke-width='1.15'/>
<path d='M15 26.5h2v1.2h-2z' fill='#C7CBD0'/>
"""

def worker_pose(*, hanging=False, arm='arm-down'):
    # Вкладений viewport обмежує згладжений рисунок власним кадром.
    lower = 'feet-hang' if hanging else 'feet-down'
    lanyard = "<use href='#lanyard'/>" if hanging else ''
    harness = "<use href='#harness'/>" if hanging else ''
    return (f"<svg x='0' y='0' width='{FW}' height='{BODY}' viewBox='0 0 32 44' shape-rendering='geometricPrecision'>"
            f"{lanyard}<use href='#{lower}'/><use href='#{arm}'/><use href='#right-arm'/><use href='#upper'/>{harness}</svg>")


# Спільний контур на падінні, підвісі та в каскаді, з тонким темним краєм для світлого фону.
DOLLAR_ART = """
<linearGradient id='emerald' x1='0' y1='0' x2='.25' y2='1'>
  <stop stop-color='#B2FFD1'/>
  <stop offset='.44' stop-color='#58F4A1'/>
  <stop offset='1' stop-color='#1ECD79'/>
</linearGradient>
<path id='dollar' d='M6.45 3.15C5.93 2.41 5.09 2.05 4.03 2.05c-1.4 0-2.31.73-2.31 1.76 0 1.09.96 1.58 2.38 1.96 1.56.41 2.31.94 2.31 2.04 0 1.24-1.03 2.16-2.54 2.16-1.09 0-2.03-.44-2.69-1.19M4.03 1.02v10.1' fill='none' stroke-linecap='round' stroke-linejoin='round'/>
"""
COIN = [".YY.", "YHYy", "YYYy", ".yy."]
WAVE_POSES = ('h', 'reach', 'wave', 'flick', 'wave', 'reach')
WAVE_STEPS = 2 * len(WAVE_POSES)
RAIN_STEPS = 24
MOBILE_SCALE = .62
FRAMES = {'wave': 0, 'idle': WAVE_STEPS, 'land': WAVE_STEPS + 1, 'rain': WAVE_STEPS + 2,
          'cash': WAVE_STEPS + RAIN_STEPS + 2, 'hang': WAVE_STEPS + RAIN_STEPS + 3,
          'count': WAVE_STEPS + RAIN_STEPS + 4}
# Розмір, смуга, фаза, поперечний дрейф і видимість кожного знака під гаком.
RAIN_PARTICLES = (
    ('d', 3.1, 0, -1.6, .94),
    ('d-small', 11.5, 3, 1.2, .72),
    ('d-large', 5.8, 7, -.8, 1),
    ('d-small', 2, 10, -1.1, .62),
    ('d', 9.9, 14, 1.9, .88),
    ('d-small', 2.6, 17, -1.6, .76),
    ('d', 6.9, 21, -1.2, .85),
)


def dollar(x, y, width=4, height=6, opacity=1):
    return (f"<svg x='{x}' y='{y}' width='{width}' height='{height}' viewBox='0 0 8 12' opacity='{opacity}' shape-rendering='geometricPrecision'>"
            "<use href='#dollar' stroke='#064434' stroke-opacity='.76' stroke-width='2.05'/>"
            "<use href='#dollar' stroke='url(#emerald)' stroke-width='1.25'/></svg>")


def impact_dollars():
    marks = ''.join(dollar(*mark) for mark in (
        (1, 17, 7, 10, .64), (11, 8, 8, 12, .81), (22, 0, 10, 15, .95),
        (32, 14, 7, 10, .68), (39, 4, 8, 12, .84), (46, 19, 6, 9, .55),
    ))
    return f"<svg xmlns='http://www.w3.org/2000/svg' width='54' height='30' viewBox='0 0 54 30'><defs>{DOLLAR_ART}</defs>{marks}</svg>"


def coin_cells():
    return ''.join(f"<rect x='{x}' y='{y}' width='1' height='1' fill='{PAL[colour]}'/>"
                   for y, row in enumerate(COIN) for x, colour in enumerate(row) if colour != '.')


def sheet():
    """Складені SVG-пози й частинки як посилання на спільні фігури."""
    worker_parts = {
        'upper': WORKER_UPPER, 'feet-down': FEET_DOWN, 'feet-hang': FEET_HANG,
        'arm-down': LEFT_DOWN, 'arm-reach': LEFT_REACH, 'arm-wave': LEFT_WAVE,
        'arm-flick': LEFT_FLICK, 'right-arm': RIGHT_ARM, 'lanyard': LANYARD, 'harness': HARNESS,
    }
    figures = {
        'i': worker_pose(), 'h': worker_pose(hanging=True),
        'reach': worker_pose(hanging=True, arm='arm-reach'), 'wave': worker_pose(hanging=True, arm='arm-wave'),
        'flick': worker_pose(hanging=True, arm='arm-flick'),
        'land': ''.join(dollar(*mark) for mark in (
            (0, 17, 3, 5, .58), (3, 15, 4, 6, .83), (7, 14, 5, 8, 1),
            (12, 17, 4, 5, .77), (12, 12, 3, 5, .6),
        )),
        'cash': dollar(5, 1, 5, 8) + dollar(10, 5, 3, 5, .72),
        'c': coin_cells(), 'd': dollar(0, 0), 'd-small': dollar(0, 0, 3, 5), 'd-large': dollar(0, 0, 5, 8),
    }
    defs = WORKER_PAINT + DOLLAR_ART + ''.join(f"<g id='{key}'>{shape}</g>" for key, shape in (worker_parts | figures).items())

    def use(ref, x, y=0, *, mirror=False, opacity=1):
        placement = f"transform='translate({x + FW} {y}) scale(-1 1)'" if mirror else f"x='{x}' y='{y}'"
        return f"<use href='#{ref}' {placement} opacity='{opacity}'/>"

    body = ''
    for f, pose in enumerate(WAVE_POSES * 2):
        body += use(pose, f * FW, mirror=f >= len(WAVE_POSES))
        for x, phase in ((2, 0), (10, WAVE_STEPS // 2)):
            y = BODY + 1 + ((f + phase) % WAVE_STEPS) * 2
            if y + 4 <= FH:
                body += use('c', f * FW + x, y)
    body += use('i', FRAMES['idle'] * FW) + use('land', FRAMES['land'] * FW)
    for f in range(RAIN_STEPS):
        x = (FRAMES['rain'] + f) * FW
        body += use('cash', x)
        for ref, lane, phase, drift, brightness in RAIN_PARTICLES:
            age = (f + phase) % RAIN_STEPS
            if age:
                progress = age / RAIN_STEPS
                column = lane + drift * progress
                row = 9 + 27 * progress ** 1.18
                fade = min(1, age / 4, (RAIN_STEPS - age) / 7)
                body += use(ref, round(x + column, 2), round(row, 2), opacity=round(fade * brightness, 2))
    body += use('cash', FRAMES['cash'] * FW) + use('h', FRAMES['hang'] * FW)
    w = FRAMES['count'] * FW
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{w * 3}' height='{FH * 3}' viewBox='0 0 {w} {FH}' shape-rendering='crispEdges'>"
            f"<defs>{defs}</defs>{body}</svg>")


CYL = ("<linearGradient id='c' x1='0' x2='1' y1='0' y2='0'><stop offset='0' stop-color='#11161C'/><stop offset='.14' stop-color='#4A535E'/><stop offset='.38' stop-color='#C9D1DA'/>"
       "<stop offset='.48' stop-color='#F4F6F8'/><stop offset='.64' stop-color='#8D98A4'/><stop offset='.9' stop-color='#343C46'/><stop offset='1' stop-color='#11161C'/></linearGradient>")
# сталевий канат: циліндр і звивка сталок
ROPE = ("<svg xmlns='http://www.w3.org/2000/svg' width='8' height='12' viewBox='0 0 8 12'><defs>" + CYL + "</defs><rect width='8' height='12' fill='url(#c)'/>"
        "<g stroke='#11161C' stroke-opacity='.62' stroke-width='.9'><path d='M-1 4.2 L9 -.8'/><path d='M-1 10.2 L9 5.2'/><path d='M-1 16.2 L9 11.2'/></g>"
        "<g stroke='#FFFFFF' stroke-opacity='.38' stroke-width='.5'><path d='M-1 5.4 L9 .4'/><path d='M-1 11.4 L9 6.4'/><path d='M-1 17.4 L9 12.4'/></g></svg>")
# гакова підвіска: щоки зі шківом, траверса, кований гак змінного перерізу із защіпкою
HOOK = ("<svg xmlns='http://www.w3.org/2000/svg' width='64' height='120' viewBox='0 0 64 120'><defs>" + CYL +
        "<linearGradient id='k' x1='0' x2='1' y1='0' y2='1'><stop offset='0' stop-color='#DDE3EA'/><stop offset='.32' stop-color='#8D98A4'/><stop offset='.7' stop-color='#3A434E'/><stop offset='1' stop-color='#171C22'/></linearGradient>"
        "<linearGradient id='f' x1='0' x2='1' y1='0' y2='0'><stop offset='0' stop-color='#1B2129'/><stop offset='.3' stop-color='#6E7985'/><stop offset='.52' stop-color='#C9D1DA'/><stop offset='.74' stop-color='#56606C'/><stop offset='1' stop-color='#11161C'/></linearGradient>"
        "<radialGradient id='n' cx='.36' cy='.32' r='.8'><stop offset='0' stop-color='#F4F6F8'/><stop offset='.5' stop-color='#8D98A4'/><stop offset='1' stop-color='#232A32'/></radialGradient></defs>"
        "<rect x='16' y='4' width='32' height='38' rx='13' fill='url(#k)' stroke='#11161C' stroke-width='1'/>"
        "<path d='M19 16 a13 13 0 0 1 13 -11.4' fill='none' stroke='#FFFFFF' stroke-opacity='.7' stroke-width='.9'/>"
        "<circle cx='32' cy='21' r='10' fill='#232A32' stroke='#11161C' stroke-width='.8'/><circle cx='32' cy='21' r='8.2' fill='none' stroke='#8D98A4' stroke-width='1.3'/>"
        "<circle cx='32' cy='21' r='4.6' fill='url(#n)' stroke='#11161C' stroke-width='.8'/><path d='M32 18.6 l2.1 1.2 v2.4 l-2.1 1.2 l-2.1 -1.2 v-2.4 z' fill='#232A32'/>"
        "<g fill='url(#n)' stroke='#11161C' stroke-width='.5'><circle cx='21.5' cy='35' r='1.6'/><circle cx='42.5' cy='35' r='1.6'/></g>"
        "<rect x='23' y='41' width='18' height='6.5' rx='1.2' fill='url(#c)' stroke='#11161C' stroke-width='.8'/>"
        "<path d='M28 47 L28 58 C28 64 47 66 49 82 C50 98 36 108 24 104 C16 101 11 93 12 84 L17 84 C17 91 22 96 28 96 C36 96 41 90 40 82 C39 72 36 68 36 58 L36 47 Z' fill='url(#f)' stroke='#11161C' stroke-width='1' stroke-linejoin='round'/>"
        "<path d='M46.6 80 C47.6 94 36 104 25 101.2' fill='none' stroke='#FFFFFF' stroke-opacity='.5' stroke-width='1.1' stroke-linecap='round'/>"
        "<path d='M31.6 49 V58' stroke='#FFFFFF' stroke-opacity='.55' stroke-width='.9'/>"
        "<path d='M29.5 61 L15.2 85.2' stroke='#11161C' stroke-width='2.8' stroke-linecap='round'/><path d='M29.5 61 L15.2 85.2' stroke='#AEB8C3' stroke-width='1.3' stroke-linecap='round'/>"
        "<circle cx='29.5' cy='61' r='1.7' fill='url(#n)' stroke='#11161C' stroke-width='.5'/></svg>")


def uri(svg):
    """Мінімальне екранування для url("…") у CSS: лише символи, що ламають URL або рядок."""
    assert '"' not in svg and '%' not in svg
    svg = ''.join(line.strip() for line in svg.splitlines())
    return 'url("data:image/svg+xml,' + svg.replace('#', '%23').replace('<', '%3C').replace('>', '%3E') + '")'


def px(frame):
    return f'-{frame * FW * CELL}px' if frame else '0'


def css_block():
    travel = 'min(560px,calc(100vh - var(--nav-h,64px) - 290px))'
    move = '.28s cubic-bezier(.2,.7,.2,1)'
    sw, sh = FRAMES['count'] * FW * CELL, FH * CELL
    mobile = MOBILE_SCALE
    fw, body_h = FW * CELL, BODY * CELL
    rules = f'''{BEGIN}
/* кран-глибиномір: сталевий канат виходить просто з гусениці прогресу, на ньому гакова підвіска. Гак опускається з прокруткою;
   унизу сторінки підчіплює будівельника за підвіс і підіймає його, коли гортаєш назад (махає, губить монети). Клік по вантажу — він
   падає, лишаючи смарагдові знаки долара. Під час повторного підйому вони сиплються з гака. Стан — класи на #gauge
   (web/js/site.js): has-load, is-lifting, is-falling, is-splat, is-mush. Рух вимикається reduced-motion, static і паузою. */
P .gauge{{--crane-h:{travel};top:calc(var(--nav-h,64px) + 21px);transform:none;height:var(--crane-h);transition:opacity .6s,top .45s var(--ease);clip-path:inset(-8px -420px -190px -420px)}}
P .track.is-up ~ .gauge{{top:21px}}
P .gauge__scale{{opacity:1;z-index:2;width:11px;height:7px;top:-7px;bottom:auto;left:50%;margin-left:-5.5px;background:linear-gradient(90deg,#11161C,#56606C 16%,#C9D1DA 40%,#F4F6F8 50%,#8D98A4 66%,#343C46 90%,#11161C);clip-path:polygon(0 0,100% 0,78% 100%,22% 100%)}}
P .gauge__scale i,P .gauge__stops,P .s-cine.is-pinned .cine__rail{{display:none}}
P .gauge__float{{z-index:1;width:44px;height:82.5px;margin:0 0 0 -22px;border-radius:0;background:{uri(HOOK)} center/44px 82.5px no-repeat;box-shadow:none;filter:drop-shadow(0 5px 6px rgba(2,7,22,.6));transition:transform {move}}}
P .gauge__float::before{{content:"";position:absolute;left:50%;bottom:calc(100% - 5px);width:5px;margin-left:-2.5px;height:calc(var(--crane-h) + 12px);background:{uri(ROPE)} center bottom/5px 7.5px repeat-y}}
P .gauge::after,P .gauge.has-load .gauge__float::after{{content:"";position:absolute;left:50%;width:{fw}px;margin-left:-19px;background:{uri(sheet())} {px(FRAMES['idle'])} 0/{sw}px {sh}px no-repeat}}
P .gauge::after{{top:calc(100% + 63px);height:{body_h}px;filter:drop-shadow(0 3px 4px rgba(2,7,22,.5))}}
P .gauge.has-load::after{{display:none}}
P .gauge.has-load .gauge__float{{cursor:pointer}}
/* підхоплення: вантаж пружинить на гаку, далі гойдається */
P .gauge.has-load .gauge__float::after{{top:63px;height:{sh}px;background-position-x:{px(FRAMES['hang'])};transform-origin:50% -4px;animation:load-catch .5s cubic-bezier(.3,1.7,.5,1) both,load-sway 2.6s ease-in-out .5s infinite alternate}}
P .gauge.has-load.is-lifting .gauge__float::after{{animation:load-sway 2.6s ease-in-out infinite alternate,load-wave .64s steps({WAVE_STEPS}) infinite}}
P .gauge.has-load.is-mush .gauge__float::after{{background-position-x:{px(FRAMES['cash'])}}}
P .gauge.has-load.is-mush.is-lifting .gauge__float::after{{animation:load-sway 2.6s ease-in-out infinite alternate,dollar-rain .64s steps({RAIN_STEPS}) infinite}}
@keyframes load-catch{{from{{transform:translateY(7px) scale(1.18,.78)}}to{{transform:none}}}}
@keyframes load-sway{{from{{transform:rotate(-4deg)}}to{{transform:rotate(4deg)}}}}
@keyframes load-wave{{from{{background-position-x:{px(FRAMES['wave'])}}}to{{background-position-x:{px(FRAMES['idle'])}}}}}
@keyframes dollar-rain{{from{{background-position-x:{px(FRAMES['rain'])}}}to{{background-position-x:{px(FRAMES['cash'])}}}}}
/* падіння: прискорення й оберт; тривалість задає JS (∝ √висоти) */
P .gauge.is-falling::after{{background-position-x:{px(2)};animation:load-drop var(--drop-t,.7s) cubic-bezier(.5,0,1,.6) both}}
P .gauge.is-mush.is-falling::after{{background-position-x:{px(FRAMES['cash'])}}}
@keyframes load-drop{{from{{transform:translateY(var(--drop,0px)) rotate(0deg)}}to{{transform:translateY(0) rotate(80deg)}}}}
/* приземлення: знаки долара, коротке кільце й поштовх крана. Шар ефектів — <output class="gauge__m">, підпис якого прибрано */
P .gauge.is-splat::after{{background-position-x:{px(FRAMES['land'])}}}
P .gauge.is-splat{{animation:crane-jolt .3s cubic-bezier(.3,0,.2,1)}}
P .gauge__m{{display:block;left:50%;top:calc(100% + {63 + body_h}px);width:0;height:0;margin:0 0 0 -3px;padding:0;background:none;font-size:0;transform:none;pointer-events:none}}
P .gauge__m::before,P .gauge__m::after{{content:"";position:absolute;opacity:0}}
P .gauge__m::before{{left:-30px;top:-5px;width:60px;height:10px;border-radius:50%;border:1.5px solid rgba(221,227,234,.9)}}
P .gauge__m::after{{left:-27px;top:-27px;width:54px;height:30px;background:{uri(impact_dollars())} center/contain no-repeat;transform-origin:50% 100%}}
P .gauge.is-splat .gauge__m::before{{animation:impact-ring .5s cubic-bezier(.16,1,.3,1)}}
P .gauge.is-splat .gauge__m::after{{animation:impact-burst .6s cubic-bezier(.16,1,.3,1)}}
@keyframes crane-jolt{{0%{{transform:translateY(0)}}30%{{transform:translateY(3px)}}60%{{transform:translateY(-1px)}}100%{{transform:translateY(0)}}}}
@keyframes impact-ring{{from{{opacity:.9;transform:scale(.15)}}to{{opacity:0;transform:scale(1)}}}}
@keyframes impact-burst{{0%{{opacity:0;transform:scale(.35)}}24%{{opacity:.95}}70%{{opacity:.8;transform:translateY(-9px) scale(1)}}100%{{opacity:0;transform:translateY(1px) scale(1)}}}}
[data-quality=static]P .gauge.has-load .gauge__float::after,[data-quality=static]P .gauge.is-splat,[data-quality=static]P .gauge.is-splat .gauge__m::before,[data-quality=static]P .gauge.is-splat .gauge__m::after{{animation:none}}
@media (max-height:640px){{P .gauge::after,P .gauge.has-load .gauge__float::after,P .gauge__m{{display:none}}}}
/* телефон і планшет: той самий кран у масштабі {mobile}, впритул до правого краю. Хід рахується так, щоб вантаж стояв над нижньою
   панеллю; сам кран не ловить дотиків (кнопки карток під ним працюють), ловить лише вантаж на гаку. Поштовх при ударі вимкнено,
   бо він анімує transform, яким тут задано масштаб. */
@media (max-width:1023px){{
  P .gauge{{display:block;right:3px;top:calc(var(--nav-h,64px) + {14 + 7 * mobile:.2f}px);--crane-h:calc((100svh - var(--nav-h,64px) - 172px) / {mobile});transform:scale({mobile});transform-origin:top right;pointer-events:none}}
  P .track.is-up ~ .gauge{{top:{14 + 7 * mobile:.2f}px}}
  P .gauge.has-load .gauge__float{{pointer-events:auto}}
  P .gauge.is-splat{{animation:none}}
}}
{END}'''
    return rules.replace('P ', P + ' ').replace(']P', ']' + P)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    block = css_block()
    print(f"аркуш кадрів: {FRAMES['count']} × {FW * CELL}×{FH * CELL} px; блок CSS {len(block.encode('utf-8'))} байтів")
    if '--write' in sys.argv or '--check' in sys.argv:
        s = CSS.read_text(encoding='utf-8')
        if s.count(BEGIN) != 1 or s.count(END) != 1:
            sys.exit('у site.css немає рівно однієї пари маркерів crane')
        a, b = s.index(BEGIN), s.index(END) + len(END)
        if '--check' in sys.argv:
            if s[a:b] != block:
                sys.exit('блок crane у site.css не відповідає tools/crane.py — запустіть --write')
        else:
            CSS.write_text(s[:a] + block + s[b:], encoding='utf-8')


if __name__ == '__main__':
    main()
