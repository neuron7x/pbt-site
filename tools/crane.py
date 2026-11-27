#!/usr/bin/env python3
"""Кран-глибиномір теми «Сталь»: канат, гакова підвіска, вантаж і його кадри — згенеровано, а не вставлено руками.

Вся графіка — власна, намальована тут: SVG у data-URI всередині web/css/site.css (CSP: img-src data:), без файлів і запитів.
Будівельник — оригінальний векторний персонаж у палітрі бренду; чужих спрайтів і торгових марок немає (docs/PROVENANCE.md).

Кадр 16×44 клітинки, клітинка 2 px (постать 32×44 px):
  0–7   вантаж махає руками, падають монети (під час підйому)
  8     будівельник стоїть унизу
  9     пляма після падіння
  10–17 грудка: тече й крапає (під час підйому)
  18    грудка у спокої
  19    будівельник висить на гаку

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
PAL = {'Y': '#FDC501', 'y': '#C99700', 'H': '#FFE98A', 'B': '#1238A8', 'R': '#C81E1E', 'r': '#8E1212', 'P': '#E86A6A'}
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

def worker_pose(*, hanging=False, waving=False):
    # Вкладений viewport обмежує рисунок власним кадром. Монети й бризки
    # використовують окремі піксельні фігури, тому контур постаті згладжується тут.
    arm = LEFT_WAVE if waving else LEFT_DOWN
    legs = FEET_HANG if hanging else FEET_DOWN
    lanyard = LANYARD if hanging else ''
    harness = HARNESS if hanging else ''
    return (f"<svg x='0' y='0' width='{FW}' height='{BODY}' viewBox='0 0 32 44' shape-rendering='geometricPrecision'>"
            f"{lanyard}{legs}{arm}{RIGHT_ARM}{WORKER_UPPER}{harness}</svg>")

COIN = [".YY.", "YHYy", "YYYy", ".yy."]
SPLAT = {18: "R..............r", 19: "....yYYYYYYy....", 20: ".rRRRRRRRRRRRRr.", 21: "RRRRrRRRRRRrRRRR"}
MUSH = ["......yYYy......", ".....RRRRRR.....", "....RRrRRPRR....", "...RRRRRRRrRR...", "..RRrRRPRRRRRR..", "..RRRRRrRRRPRR..",
        "..RrRRRRRRRRRR..", "...RRRPRRrRRR...", "...rRRRRRRRRR...", "....RRRrRRRR....", ".....RRPRRR.....", "......RRRR......", ".......RR......."]
MUSH_B = MUSH[:7] + ["." + r[:-1] for r in MUSH[7:]]
DROP, BIT = ["R", "R", "r"], ["Rr", "rR"]
assert all(len(r) == FW for r in MUSH + MUSH_B + list(SPLAT.values()))
MOBILE_SCALE = .62                                         # масштаб крана на екранах вужчих за 1024 px
FRAMES = {'wave': 0, 'idle': 8, 'splat': 9, 'drip': 10, 'mush': 18, 'hang': 19, 'count': 20}


def cells(rows, ox, oy):
    """Рядки клітинок → <rect> із серіями однакового кольору."""
    out = ''
    for y, row in (rows.items() if isinstance(rows, dict) else enumerate(rows)):
        x = 0
        while x < len(row):
            ch, x0 = row[x], x
            while x < len(row) and row[x] == ch:
                x += 1
            if ch != '.':
                out += f"<rect x='{ox + x0}' y='{oy + y}' width='{x - x0}' height='1' fill='{PAL[ch]}'/>"
    return out


def sheet():
    """Кожну позу й частинку описано один раз у <defs>; кадри — посилання <use>. Дзеркальна поза — те саме з scale(-1,1)."""
    poses = (('w', worker_pose(hanging=True, waving=True)), ('i', worker_pose()), ('h', worker_pose(hanging=True)))
    effects = (('s', SPLAT), ('m', MUSH), ('n', MUSH_B), ('c', COIN), ('d', DROP), ('b', BIT))
    defs = WORKER_PAINT + ''.join(f"<g id='{key}'>{pose}</g>" for key, pose in poses)
    defs += ''.join(f"<g id='{key}'>{cells(rows, 0, 0)}</g>" for key, rows in effects)

    def use(ref, x, y=0, mirror=False):
        if mirror:
            return f"<use href='#{ref}' transform='translate({x + FW} {y}) scale(-1 1)'/>"
        return f"<use href='#{ref}' x='{x}'" + (f" y='{y}'" if y else '') + "/>"

    def falling(parts, frame, f, start):
        """Частинки під вантажем: зсув 3 клітинки на кадр, цикл 8 кадрів; що вийшло за кадр — не малюємо."""
        out = ''
        for ref, height, cx, phase in parts:
            cy = start + ((f + phase) % 8) * 3
            if cy + height <= FH:
                out += use(ref, frame * FW + cx, cy)
        return out

    body = ''
    for f in range(8):
        body += use('w', f * FW, mirror=(f // 2) % 2 == 1)
        body += falling((('c', 4, 2, 0), ('c', 4, 10, 4)), f, f, BODY + 1)
    body += use('i', FRAMES['idle'] * FW) + use('s', FRAMES['splat'] * FW)
    for f in range(8):
        g = FRAMES['drip'] + f
        body += use('m' if (f // 2) % 2 == 0 else 'n', g * FW)
        body += falling((('d', 3, 4, 0), ('b', 2, 9, 3), ('d', 3, 12, 5)), g, f, len(MUSH) + 1)
    body += use('m', FRAMES['mush'] * FW) + use('h', FRAMES['hang'] * FW)
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


def burst(colour, pts):
    """Частинки удару: одна клітинка 2 px і її тіні в точках (x, y)."""
    return ','.join(f'{x}px {y}px 0 {colour}' for x, y in pts)


def css_block():
    travel = 'min(560px,calc(100vh - var(--nav-h,64px) - 290px))'
    move = '.28s cubic-bezier(.2,.7,.2,1)'
    sw, sh = FRAMES['count'] * FW * CELL, FH * CELL
    mobile = MOBILE_SCALE
    fw, body_h = FW * CELL, BODY * CELL
    drops = burst('#C81E1E', [(-26, -10), (-18, -22), (-9, -30), (4, -34), (15, -27), (24, -16), (30, -6), (-32, -3), (10, -14), (-14, -9)])
    rules = f'''{BEGIN}
/* кран-глибиномір: сталевий канат виходить просто з гусениці прогресу, на ньому гакова підвіска. Гак опускається з прокруткою;
   унизу сторінки підчіплює будівельника за підвіс і підіймає його, коли гортаєш назад (махає, губить монети). Клік по вантажу — він
   зривається, падає туди, де стояв, і лишається плямою; гак, повернувшись, бере її грудкою. Стан — класи на #gauge
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
P .gauge.has-load.is-lifting .gauge__float::after{{animation:load-sway 2.6s ease-in-out infinite alternate,load-wave .72s steps(8) infinite}}
P .gauge.has-load.is-mush .gauge__float::after{{background-position-x:{px(FRAMES['mush'])}}}
P .gauge.has-load.is-mush.is-lifting .gauge__float::after{{animation:load-sway 2.6s ease-in-out infinite alternate,mush-drip .72s steps(8) infinite}}
@keyframes load-catch{{from{{transform:translateY(7px) scale(1.18,.78)}}to{{transform:none}}}}
@keyframes load-sway{{from{{transform:rotate(-4deg)}}to{{transform:rotate(4deg)}}}}
@keyframes load-wave{{from{{background-position-x:{px(FRAMES['wave'])}}}to{{background-position-x:{px(FRAMES['wave'] + 8)}}}}}
@keyframes mush-drip{{from{{background-position-x:{px(FRAMES['drip'])}}}to{{background-position-x:{px(FRAMES['drip'] + 8)}}}}}
/* падіння: прискорення й оберт; тривалість задає JS (∝ √висоти) */
P .gauge.is-falling::after{{background-position-x:{px(2)};animation:load-drop var(--drop-t,.7s) cubic-bezier(.5,0,1,.6) both}}
P .gauge.is-mush.is-falling::after{{background-position-x:{px(FRAMES['mush'])}}}
@keyframes load-drop{{from{{transform:translateY(var(--drop,0px)) rotate(0deg)}}to{{transform:translateY(0) rotate(80deg)}}}}
/* удар: пляма, поштовх усього крана, кільце пилу й бризки. Шар ефектів — <output class="gauge__m">, підпис якого прибрано */
P .gauge.is-splat::after{{background-position-x:{px(FRAMES['splat'])}}}
P .gauge.is-splat{{animation:crane-jolt .3s cubic-bezier(.3,0,.2,1)}}
P .gauge__m{{display:block;left:50%;top:calc(100% + {63 + body_h}px);width:0;height:0;margin:0 0 0 -3px;padding:0;background:none;font-size:0;transform:none;pointer-events:none}}
P .gauge__m::before,P .gauge__m::after{{content:"";position:absolute;opacity:0}}
P .gauge__m::before{{left:-30px;top:-5px;width:60px;height:10px;border-radius:50%;border:1.5px solid rgba(221,227,234,.9)}}
P .gauge__m::after{{left:-1px;top:-2px;width:2px;height:2px;background:#C81E1E;box-shadow:{drops}}}
P .gauge.is-splat .gauge__m::before{{animation:impact-ring .5s cubic-bezier(.16,1,.3,1)}}
P .gauge.is-splat .gauge__m::after{{animation:impact-burst .6s cubic-bezier(.16,1,.3,1)}}
@keyframes crane-jolt{{0%{{transform:translateY(0)}}30%{{transform:translateY(3px)}}60%{{transform:translateY(-1px)}}100%{{transform:translateY(0)}}}}
@keyframes impact-ring{{from{{opacity:.9;transform:scale(.15)}}to{{opacity:0;transform:scale(1)}}}}
@keyframes impact-burst{{0%{{opacity:1;transform:scale(.15)}}70%{{opacity:1}}100%{{opacity:0;transform:translateY(6px) scale(1)}}}}
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
