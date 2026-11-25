#!/usr/bin/env python3
"""Небо над Полтавою і вода — палітра теми «sky», обчислена, а не підібрана. Лише stdlib, детерміновано.

Що рахується
  1. Геометрія: Полтава 49°35′N (config/business.json не чіпаємо — широта стала тут). День літнього сонцестояння,
     схилення Сонця +23,44°. Чотири моменти робочого дня за справжнім сонячним часом → висота Сонця.
  2. Небо: одноразове релеївське розсіювання. Спектр Сонця — Планк 5778 K. Оптична товща Релея
     τ(λ) = 0,008569·λ⁻⁴·(1 + 0,0113·λ⁻² + 0,00013·λ⁻⁴), λ у мкм. Озон (смуга Шаппюї) — гаусіан, 300 DU.
     Повітряна маса — Kasten–Young 1989. Яскравість у площині, перпендикулярній до Сонця, від зеніту до обрію:
       L(λ) ∝ F₀(λ)·ω·P(Θ)·m_v/(m_v − m_s)·(e^(−τ·m_s) − e^(−τ·m_v)),  P(Θ) = 3/(16π)·(1 + cos²Θ).
  3. Вода: закон Бугера–Ламберта, T(λ) = e^(−a(λ)·d), a(λ) — поглинання чистої води, d — шлях світла в метрах.
  4. Колір: CIE 1931 (аналітична апроксимація колірних функцій), XYZ → OKLab → sRGB і Display P3.

Що НЕ з фізики (чесно): світлість фону нормовано під читання (текст ≥ 4,5:1), бо екран не відтворює яскравість неба.
З моделі взято відтінок і відносну насиченість: зеніт проти обрію, ранок проти полудня, мілка вода проти глибокої.
Модель не враховує багаторазове розсіювання й аерозоль; коефіцієнти — довідкові, округлені (docs/DESIGN.md).

Умова спростування: якщо обчислений зеніт не синіший за обрій, або полуденний зеніт не синіший за вечірній, або
вода не насичується з глибиною — модель хибна; tests/test_sky_physics.py перевіряє саме це. «Синіший» = більша
синя складова −b/L в OKLab. (Перша редакція порівнювала загальну насиченість і хибно спрацьовувала при Сонці 4°:
обрій там насичений, але теплий. Критерій виправлено на синю складову; момент 19:30 замінено на 18:00, бо одноразове
розсіювання при Сонці нижче ≈10° дає зеленуватий обрій, якого без аерозолю й багаторазового розсіювання не перевірити.)

  python3 tools/sky.py            — показати палітру
  python3 tools/sky.py --write    — вписати блок між маркерами у web/css/site.css
  python3 tools/sky.py --check    — вихід 1, якщо блок у CSS не відповідає моделі
"""
import math, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / 'web' / 'css' / 'site.css'
BEGIN, END = '/* sky:begin — згенеровано tools/sky.py, руками не правити */', '/* sky:end */'
LAT, DECL = 49.5883, 23.44                       # Полтава; схилення Сонця 21 червня
MOMENTS = [('roboty', 7.0), ('cina', 12.0), ('materialy', 16.0), ('geo', 18.0)]   # секція → справжній сонячний час
WL = [380 + 5 * i for i in range(81)]            # нм


def sun_elevation(hour):
    """Висота Сонця, градуси: sin h = sin φ·sin δ + cos φ·cos δ·cos H, H = 15°·(t − 12)."""
    p, d, h = math.radians(LAT), math.radians(DECL), math.radians(15 * (hour - 12))
    return math.degrees(math.asin(math.sin(p) * math.sin(d) + math.cos(p) * math.cos(d) * math.cos(h)))


def planck(nm, t=5778.0):
    l = nm * 1e-9
    return 1.0 / (l ** 5 * (math.exp(1.4387769e-2 / (l * t)) - 1.0))


def tau_rayleigh(nm):
    u = nm / 1000.0
    return 0.008569 * u ** -4 * (1 + 0.0113 * u ** -2 + 0.00013 * u ** -4)


def tau_ozone(nm, dobson=300.0):
    """Смуга Шаппюї: гаусіан із максимумом 4,8·10⁻²¹ см² на 590 нм, σ = 55 нм; 1 DU = 2,687·10¹⁶ молекул/см²."""
    return 4.8e-21 * math.exp(-((nm - 590.0) / 55.0) ** 2 / 2) * dobson * 2.687e16


def air_mass(zenith_deg):
    z = min(zenith_deg, 89.9)
    return 1.0 / (math.cos(math.radians(z)) + 0.50572 * (96.07995 - z) ** -1.6364)


def _g(x, mu, s1, s2):
    s = s1 if x < mu else s2
    return math.exp(-0.5 * ((x - mu) / s) ** 2)


def cmf(nm):
    """CIE 1931 2°: багатопелюсткова гаусова апроксимація (Wyman, Sloan, Shirley, JCGT 2013)."""
    x = 1.056 * _g(nm, 599.8, 37.9, 31.0) + 0.362 * _g(nm, 442.0, 16.0, 26.7) - 0.065 * _g(nm, 501.1, 20.4, 26.2)
    y = 0.821 * _g(nm, 568.8, 46.9, 40.5) + 0.286 * _g(nm, 530.9, 16.3, 31.1)
    z = 1.217 * _g(nm, 437.0, 11.8, 36.0) + 0.681 * _g(nm, 459.0, 26.0, 13.8)
    return x, y, z


def to_xyz(spectrum):
    X = Y = Z = 0.0
    for nm, v in zip(WL, spectrum):
        x, y, z = cmf(nm)
        X += v * x; Y += v * y; Z += v * z
    return X, Y, Z


def sky_spectrum(sun_el, view_zenith):
    zs = 90.0 - sun_el
    ms, mv = air_mass(zs), air_mass(view_zenith)
    cos_t = math.cos(math.radians(zs)) * math.cos(math.radians(view_zenith))     # азимут 90° від Сонця
    phase = 3 / (16 * math.pi) * (1 + cos_t ** 2)
    out = []
    for nm in WL:
        tr = tau_rayleigh(nm); t = tr + tau_ozone(nm)
        geo = mv * math.exp(-t * ms) * t if abs(mv - ms) < 1e-6 else mv / (mv - ms) * (math.exp(-t * ms) - math.exp(-t * mv))
        out.append(planck(nm) * (tr / t) * phase * geo)
    return out


# поглинання чистої води, м⁻¹ (Pope & Fry 1997 до 700 нм, далі Kou et al. 1993; округлено, лінійна інтерполяція)
WATER = [(380, 0.0114), (400, 0.0066), (420, 0.0045), (440, 0.0064), (460, 0.0098), (480, 0.0127), (500, 0.0204), (520, 0.0409),
         (540, 0.0474), (560, 0.0619), (580, 0.0896), (600, 0.2224), (620, 0.2755), (640, 0.3108), (660, 0.4100), (680, 0.4650),
         (700, 0.6240), (720, 1.2310), (740, 2.3800), (760, 2.5500), (780, 2.3600)]


def water_a(nm):
    for (l0, a0), (l1, a1) in zip(WATER, WATER[1:]):
        if l0 <= nm <= l1:
            return a0 + (a1 - a0) * (nm - l0) / (l1 - l0)
    raise ValueError(nm)


def water_spectrum(depth_m):
    """Денне світло (Планк 6504 K), що пройшло d метрів води."""
    return [planck(nm, 6504.0) * math.exp(-water_a(nm) * depth_m) for nm in WL]


WHITE = to_xyz([planck(nm, 6504.0) for nm in WL])


def xyz_to_lin(xyz, p3=False):
    X, Y, Z = (c / WHITE[1] for c in xyz)
    Xw, Yw, Zw = (c / WHITE[1] for c in WHITE)
    X, Y, Z = X * 0.95047 / Xw, Y, Z * 1.08883 / Zw                      # адаптація до D65 масштабуванням (von Kries у XYZ)
    if p3:
        return (2.4934969 * X - 0.9313836 * Y - 0.4027108 * Z, -0.8294890 * X + 1.7626641 * Y + 0.0236247 * Z, 0.0358458 * X - 0.0761724 * Y + 0.9568845 * Z)
    return (3.2404542 * X - 1.5371385 * Y - 0.4985314 * Z, -0.9692660 * X + 1.8760108 * Y + 0.0415560 * Z, 0.0556434 * X - 0.2040259 * Y + 1.0572252 * Z)


def lin_to_oklab(rgb):
    r, g, b = rgb
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (math.copysign(abs(v) ** (1 / 3), v) for v in (l, m, s))
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s, 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s, 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def oklab_to_lin(lab):
    L, a, b = lab
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s, -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


SRGB_TO_P3 = ((0.8224621, 0.1775380, 0.0), (0.0331941, 0.9668058, 0.0), (0.0170827, 0.0723974, 0.9105199))


def enc(v):
    v = min(max(v, 0.0), 1.0)
    return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def hue_sat(xyz):
    """Відтінок і насиченість (C/L) в OKLab із колориметрії; яскравість відкинуто."""
    y = xyz[1]
    L, a, b = lin_to_oklab(xyz_to_lin(tuple(c / y * WHITE[1] * 0.6 for c in xyz)))
    return math.atan2(b, a), math.hypot(a, b) / L, -b / L


def fit(L, hue, chroma, p3=False):
    """Найбільша насиченість ≤ chroma, що вміщується в охоплення; повертає (r,g,b) кодовані 0…1."""
    c = chroma
    while True:
        lin = oklab_to_lin((L, c * math.cos(hue), c * math.sin(hue)))
        if p3:
            lin = tuple(sum(k * v for k, v in zip(row, lin)) for row in SRGB_TO_P3)
        if all(-1e-4 <= v <= 1 + 1e-4 for v in lin) or c < 1e-4:
            return tuple(enc(v) for v in lin), c
        c -= 0.001


def hexc(rgb):
    return '#' + ''.join(f'{round(v * 255):02X}' for v in rgb)


def rel_lum(hexstr):
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hexstr[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a, b):
    la, lb = sorted((rel_lum(a), rel_lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# ── ролі ──
SKY_STOPS = [(0.0, 0, 0.815), (0.34, 55, 0.855), (0.68, 76, 0.895), (1.0, 86, 0.915)]   # (позиція у секції, зенітний кут погляду, світлість OKLab)
SKY_GAIN = 0.62          # єдиний множник насиченості для всього неба: відносні відмінності лишаються з моделі
WATER_ROLES = [('ice-0', 0.5, 0.975), ('ice', 1.5, 0.95), ('ice-2', 3.0, 0.915), ('pool', 5.5, 0.86), ('deep', 26.0, 0.31), ('abyss', 60.0, 0.19)]   # (роль, шлях у воді м, світлість)
WATER_GAIN = 0.55
TEXT = {'ink': '#08142A', 'ink-2': '#2A3A55', 'ink-3': '#3A4B6B', 'accent': '#1238A8'}       # текст на небі: перевіряється на кожній зупинці


def palette():
    out = {'moments': [], 'water': [], 'physics': {}}
    for sec, hour in MOMENTS:
        el = sun_elevation(hour); stops = []
        for pos, vz, L in SKY_STOPS:
            hue, sat, blue = hue_sat(to_xyz(sky_spectrum(el, vz)))
            (rgb, c), (p3, c3) = fit(L, hue, sat * L * SKY_GAIN), fit(L, hue, sat * L * SKY_GAIN, p3=True)
            stops.append({'pos': pos, 'view': vz, 'hex': hexc(rgb), 'p3': p3, 'hue': math.degrees(hue) % 360, 'sat': sat, 'blue': blue, 'c': c, 'c3': c3})
        out['moments'].append({'sec': sec, 'hour': hour, 'el': el, 'stops': stops})
    for role, d, L in WATER_ROLES:
        hue, sat, _ = hue_sat(to_xyz(water_spectrum(d)))
        (rgb, c), (p3, c3) = fit(L, hue, sat * L * WATER_GAIN), fit(L, hue, sat * L * WATER_GAIN, p3=True)
        out['water'].append({'role': role, 'd': d, 'hex': hexc(rgb), 'p3': p3, 'hue': math.degrees(hue) % 360, 'sat': sat, 'c': c})
    return out


def css_block(p):
    P = ':is(:root[data-theme="sky"],:root:not([data-theme]))'
    def grad(stops, key):
        col = (lambda s: s['hex']) if key == 'hex' else (lambda s: 'color(display-p3 %.4f %.4f %.4f)' % s['p3'])
        first = stops[0]
        return ('linear-gradient(180deg,' + col(first) + ' 0,' + col(first) + ' var(--a-limb-h),'
                + ','.join(f"{col(s)} {round(s['pos'] * 100)}%" for s in stops[1:]) + ')')
    lines = [BEGIN]
    for key in ('hex', 'p3'):
        body = []
        for m in p['moments']:
            body.append(f"{P} #{m['sec']}{{--a-sky:{grad(m['stops'], key)};--a-zenith:{m['stops'][0]['hex'] if key == 'hex' else 'color(display-p3 %.4f %.4f %.4f)' % m['stops'][0]['p3']}}}")
        w = ';'.join(f"--w-{x['role']}:{x['hex'] if key == 'hex' else 'color(display-p3 %.4f %.4f %.4f)' % x['p3']}" for x in p['water'])
        z = p['moments'][0]['stops'][0]
        rise = z['hex'] if key == 'hex' else 'color(display-p3 %.4f %.4f %.4f)' % z['p3']
        body.append(f"{P}{{--a-rise:{rise};{w}}}")
        if key == 'hex':
            lines += [f"/* {m['sec']}: сонячний час {m['hour']:g}, висота Сонця {m['el']:.2f}° */" for m in p['moments']] + body
        else:
            lines += ['@media (color-gamut:p3){'] + body + ['}']
    lines.append(END)
    return '\n'.join(lines)


def audit(p):
    """Перевірки моделі й читання; повертає список порушень."""
    bad = []
    for m in p['moments']:
        z, h = m['stops'][0], m['stops'][-1]
        if not z['blue'] > h['blue']:
            bad.append(f"{m['sec']}: зеніт не синіший за обрій")
        for s in m['stops']:
            for name, col in TEXT.items():
                need = 3.0 if name == 'accent' else 4.5
                if contrast(col, s['hex']) < need:
                    bad.append(f"{m['sec']} {s['hex']}: {name} {contrast(col, s['hex']):.2f} < {need}")
    by = {m['sec']: m for m in p['moments']}
    if not by['cina']['stops'][0]['blue'] > by['geo']['stops'][0]['blue']:
        bad.append('полуденний зеніт не синіший за вечірній')
    for x in p['water']:
        if x['role'] in ('ice-0', 'ice', 'ice-2', 'pool'):
            for name, col in TEXT.items():
                need = 3.0 if name == 'accent' else 4.5
                if contrast(col, x['hex']) < need:
                    bad.append(f"вода {x['role']} {x['hex']}: {name} {contrast(col, x['hex']):.2f} < {need}")
    sats = [x['sat'] for x in p['water']]
    if sats != sorted(sats):
        bad.append('вода не синішає з глибиною')
    return bad


def main():
    sys.stdout.reconfigure(encoding='utf-8')          # звіт українською не залежить від локалі (LC_ALL=C давав UnicodeEncodeError)
    p = palette(); block = css_block(p); bad = audit(p)
    for m in p['moments']:
        print(f"{m['sec']:10} {m['hour']:5.2f} год  Сонце {m['el']:6.2f}°  " + '  '.join(f"{s['hex']} (θ{s['view']}° h{s['hue']:.0f} s{s['sat']:.3f})" for s in m['stops']))
    for x in p['water']:
        print(f"вода {x['role']:6} d={x['d']:5.1f} м  {x['hex']}  h{x['hue']:.0f} s{x['sat']:.3f}")
    for b in bad:
        print('ПОРУШЕННЯ:', b)
    if '--write' in sys.argv or '--check' in sys.argv:
        s = CSS.read_text(encoding='utf-8')
        if s.count(BEGIN) != 1 or s.count(END) != 1:
            sys.exit('у site.css немає рівно однієї пари маркерів sky')
        a, b = s.index(BEGIN), s.index(END) + len(END)
        if '--check' in sys.argv:
            if s[a:b] != block or bad:
                sys.exit('блок sky у site.css не відповідає tools/sky.py — запустіть --write')
        else:
            if bad:
                sys.exit('палітра не пройшла перевірку — не записано')
            CSS.write_text(s[:a] + block + s[b:], encoding='utf-8')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
