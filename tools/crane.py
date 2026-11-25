#!/usr/bin/env python3
"""Кран-глибиномір теми «Сталь»: канат, гакова підвіска, вантаж і його кадри — згенеровано, а не вставлено руками.

Вся графіка — власна, намальована тут: SVG у data-URI всередині web/css/site.css (CSP: img-src data:), без файлів і запитів.
Піксельний вантаж — оригінальний персонаж у палітрі бренду; чужих спрайтів і торгових марок немає (docs/PROVENANCE.md).

Аркуш кадрів 16×44 клітинки, клітинка 2 px (постать 32×44 px):
  0–7   вантаж махає руками, падають монети (під час підйому)
  8     вантаж у спокої (стоїть унизу або висить на гаку)
  9     пляма після падіння
  10–17 грудка: тече й крапає (під час підйому)
  18    грудка у спокої

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
PAL = {'Y': '#FDC501', 'y': '#C99700', 'H': '#FFE98A', 'S': '#F2B88A', 's': '#D9925F', 'K': '#11161C', 'M': '#4A2A12', 'O': '#F97316',
       'o': '#C2540C', 'W': '#F2F5F8', 'B': '#1238A8', 'b': '#0C2878', 'G': '#9AA5B1', 'T': '#3A2414', 'R': '#C81E1E', 'r': '#8E1212', 'P': '#E86A6A'}
# вусатий будівельник у касці й сигнальному жилеті — власний персонаж; три тони на матеріал, як у спрайтах 8-бітних приставок
IDLE = ["....YYYYYYYY....", "...YHHYYYYYYY...", "..YHYYYYYYYYYY..", ".yyyyyyyyyyyyyy.", "...SSSSSSSSSS...", "..SSKSSSSSSKSS..",
        "..SSSSSssSSSSS..", "..sMMMMMMMMMMs..", "...SMMSSSSMMS...", "....SSSSSSSS....", "..OOOOOOOOOOOO..", ".OOOWWWWWWWWOOO.",
        "SOOOOOOooOOOOOOS", "SSOOWWWWWWWWOOSS", "GGOOOOOooOOOOOGG", "..BBBBBBBBBBBB..", "..BBBBBbbBBBBB..", "..BBBBB..BBBBB..",
        "..BBBB....BBBB..", "..bBBB....BBBb..", ".TTTTT....TTTTT.", ".TTTTT....TTTTT."]
WAVE = ["....YYYYYYYY....", "...YHHYYYYYYY...", "..YHYYYYYYYYYY..", "Gyyyyyyyyyyyyyy.", "S..SSSSSSSSSS...", "S.SSKSSSSSSKSS..",
        "O.SSSSSssSSSSS..", "O.sMMMMMMMMMMs..", "OO.SMMSSSSMMS...", ".OO.SSSSSSSS....", ".OOOOOOOOOOOOO..", "..OOWWWWWWWWOOO.",
        "..OOOOOooOOOOOOS", "..OOWWWWWWWWOOSS", "..OOOOOooOOOOOGG", "..BBBBBBBBBBBB..", "..BBBBBbbBBBBB..", ".BBBBB....BBBBB.",
        ".BBBB......BBBB.", "bBBB........BBBb", "TTTT........TTTT", "TTTT........TTTT"]
COIN = [".YY.", "YHYy", "YYYy", ".yy."]
SPLAT = {18: "R..............r", 19: "....yYYYYYYy....", 20: ".rRRRRRRRRRRRRr.", 21: "RRRRrRRRRRRrRRRR"}
MUSH = ["......yYYy......", ".....RRRRRR.....", "....RRrRRPRR....", "...RRRRRRRrRR...", "..RRrRRPRRRRRR..", "..RRRRRrRRRPRR..",
        "..RrRRRRRRRRRR..", "...RRRPRRrRRR...", "...rRRRRRRRRR...", "....RRRrRRRR....", ".....RRPRRR.....", "......RRRR......", ".......RR......."]
MUSH_B = MUSH[:7] + ["." + r[:-1] for r in MUSH[7:]]
DROP, BIT = ["R", "R", "r"], ["Rr", "rR"]
assert all(len(r) == FW for r in IDLE + WAVE + MUSH + MUSH_B + list(SPLAT.values())) and len(IDLE) == len(WAVE) == BODY
FRAMES = {'wave': 0, 'idle': 8, 'splat': 9, 'drip': 10, 'mush': 18, 'count': 19}


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
    defs = ''.join(f"<g id='{k}'>{cells(rows, 0, 0)}</g>" for k, rows in
                   (('w', WAVE), ('i', IDLE), ('s', SPLAT), ('m', MUSH), ('n', MUSH_B), ('c', COIN), ('d', DROP), ('b', BIT)))

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
    body += use('m', FRAMES['mush'] * FW)
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
    fw, body_h = FW * CELL, BODY * CELL
    drops = burst('#C81E1E', [(-26, -10), (-18, -22), (-9, -30), (4, -34), (15, -27), (24, -16), (30, -6), (-32, -3), (10, -14), (-14, -9)])
    rules = f'''{BEGIN}
/* кран-глибиномір: сталевий канат виходить просто з гусениці прогресу, на ньому гакова підвіска. Гак опускається з прокруткою;
   унизу сторінки підчіплює 8-бітний вантаж і підіймає його, коли гортаєш назад (махає, губить монети). Клік по вантажу — він
   зривається, падає туди, де стояв, і лишається плямою; гак, повернувшись, бере її грудкою. Стан — класи на #gauge
   (web/js/site.js): has-load, is-lifting, is-falling, is-splat, is-mush. Рух вимикається reduced-motion, static і паузою. */
P .gauge{{top:calc(var(--nav-h,64px) + 21px);transform:none;height:{travel};transition:opacity .6s,top .45s var(--ease);clip-path:inset(-8px -420px -190px -420px)}}
P .track.is-up ~ .gauge{{top:21px}}
P .gauge__scale{{opacity:1;z-index:2;width:11px;height:7px;top:-7px;bottom:auto;left:50%;margin-left:-5.5px;background:linear-gradient(90deg,#11161C,#56606C 16%,#C9D1DA 40%,#F4F6F8 50%,#8D98A4 66%,#343C46 90%,#11161C);clip-path:polygon(0 0,100% 0,78% 100%,22% 100%)}}
P .gauge__scale i,P .gauge__stops,P .s-cine.is-pinned .cine__rail{{display:none}}
P .gauge__float{{z-index:1;width:44px;height:82.5px;margin:0 0 0 -22px;border-radius:0;background:{uri(HOOK)} center/44px 82.5px no-repeat;box-shadow:none;filter:drop-shadow(0 5px 6px rgba(2,7,22,.6));transition:transform {move}}}
P .gauge__float::before{{content:"";position:absolute;left:50%;bottom:calc(100% - 5px);width:5px;margin-left:-2.5px;height:calc({travel} + 12px);background:{uri(ROPE)} center bottom/5px 7.5px repeat-y}}
P .gauge::after,P .gauge.has-load .gauge__float::after{{content:"";position:absolute;left:50%;width:{fw}px;margin-left:-19px;background:{uri(sheet())} {px(FRAMES['idle'])} 0/{sw}px {sh}px no-repeat}}
P .gauge::after{{top:calc(100% + 63px);height:{body_h}px;filter:drop-shadow(0 3px 4px rgba(2,7,22,.5))}}
P .gauge.has-load::after{{display:none}}
P .gauge.has-load .gauge__float{{cursor:pointer}}
/* підхоплення: вантаж пружинить на гаку, далі гойдається */
P .gauge.has-load .gauge__float::after{{top:63px;height:{sh}px;transform-origin:50% -4px;animation:load-catch .5s cubic-bezier(.3,1.7,.5,1) both,load-sway 2.6s ease-in-out .5s infinite alternate}}
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
