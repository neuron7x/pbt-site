#!/usr/bin/env python3
"""Look «Небо і золото» як 3D LUT (config/pbt-look.cube, 33³) — детерміновано з формул нижче, без ручного грейду.
Ціль: різна зйомка (Японія, Німеччина, США, TikTok клієнта) читається як одна серія під палітру логотипа:
  • фільмова S-крива навколо середнього сірого — щільність без зрізаних тіней;
  • розщеплене тонування: тіні → чорнило #062B5C, світла → золото #FDC501 (у хромі, яскравість зберігається);
  • вібранс: ненасичене підтягується сильніше за насичене — шкіра й небо не «кислотні»;
  • небо (h≈200–235°), жовта фарба (h≈38–60°) → sky-700 і gold; помаранчева фарба Hitachi/Hyundai/Doosan (h≈15–38°) → amber #F97316;
  • м'який відкат світлих вище 0.88 — небо без пластикового кліпу.
Запуск: python3 tools/lut.py → config/pbt-look.cube. tools/stock.py і tools/media.py застосовують його через lut3d."""
import colorsys
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'config' / 'pbt-look.cube'
N = 33
REC709 = np.array([0.2126, 0.7152, 0.0722])
INK = np.array([0x06, 0x2B, 0x5C]) / 255
GOLD = np.array([0xFD, 0xC5, 0x01]) / 255


def chroma(c):
    """Напрям кольору без яскравості: c − luma(c)."""
    return c - c @ REC709


def s_curve(x, k=0.42):
    """S-крива навколо 0.5: нахил у середині 1+k/2, на кінцях 1−k (>0 ⇒ монотонна), 0 і 1 нерухомі."""
    t = np.clip(x, 0, 1)
    return t + k * (t - t * t) * (2 * t - 1)


def rolloff(x, knee=0.88):
    over = np.maximum(x - knee, 0)
    return np.where(x > knee, knee + (1 - knee) * (1 - np.exp(-over / (1 - knee) * 1.6)) / (1 - np.exp(-1.6)), x)


def look(rgb):
    r = rgb.copy()
    y = r @ REC709
    y2 = s_curve(y)
    r = r + (y2 - y)[..., None]                                   # контраст по яскравості, кольори не зсуваються
    y = y2
    ws, wh = (1 - y) ** 2, y ** 2
    r = r + ws[..., None] * 0.10 * chroma(INK) + wh[..., None] * 0.07 * chroma(GOLD)
    flat = r.reshape(-1, 3)
    out = np.empty_like(flat)
    for i, (a, b, c) in enumerate(np.clip(flat, 0, 1)):
        h, l, s = colorsys.rgb_to_hls(a, b, c)
        deg = h * 360
        s = s * (1 + 0.34 * (1 - s))                               # вібранс
        if 200 <= deg <= 235:
            s *= 1.10; h = (h * 360 + (212 - deg) * 0.25) / 360     # небо → sky-700 (#1A87F5 ≈ 211°)
        if 15 <= deg < 38:
            s *= 1.28; h = (h * 360 + (26 - deg) * 0.20) / 360      # помаранчева фарба → amber (#F97316 ≈ 25°)
        if 38 <= deg <= 60:
            s *= 1.25; h = (h * 360 + (46 - deg) * 0.30) / 360      # жовта фарба → золото (#FDC501 ≈ 47°)
        out[i] = colorsys.hls_to_rgb(h % 1, l, min(s, 1))
    r = out.reshape(r.shape)
    r = rolloff(r)
    return np.clip(r * (1 - 0.018) + 0.018 * INK * 1.4, 0, 1)        # підняті чорні з синім відтінком — «плівкова» база


def main():
    g = np.linspace(0, 1, N)
    b, gg, rr = np.meshgrid(g, g, g, indexing='ij')                # .cube: R змінюється найшвидше
    grid = np.stack([rr, gg, b], -1).reshape(-1, 3)
    res = look(grid)
    lines = ['TITLE "PBT sky-and-gold"', f'LUT_3D_SIZE {N}', 'DOMAIN_MIN 0 0 0', 'DOMAIN_MAX 1 1 1']
    lines += [f'{x:.6f} {y:.6f} {z:.6f}' for x, y, z in res]
    out = Path(sys.argv[1]) if sys.argv[1:] else OUT              # тест пише в tmp — не перезаписує відстежуваний файл
    out.write_text('\n'.join(lines) + '\n', encoding='ascii')
    print(out, N ** 3, 'вузлів')


if __name__ == '__main__':
    main()
