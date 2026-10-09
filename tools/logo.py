#!/usr/bin/env python3
"""Логотип власника ПБТ (references/brand/, не версіюється) → активи сайту з прозорим тлом. Детерміновано, numpy + ffmpeg.
Джерело: logo-anim.mp4 1436×726, 159 кадрів 29.67 к/с — P-екскаватор, B, T-кран збираються з креслення і спалахують.
Ключ — за чистою плитою: фон анімації статичний (кадри 18–20 = кадр 20 до пікселя), тож
  alpha = smoothstep(|кадр − плита|), колір = (кадр − (1−alpha)·плита) / alpha  — точне обернення накладання «over».
Підпис «CRM» і відблиск під літерами не беремо: на публічному сайті CRM (внутрішня система) клієнтам нічого не каже. KEEP_CRM=1 — лишити.
Вихід web/media/logo/: pbt-logo.webm (VP9 з альфою, грає один раз), pbt-logo.webp/.png (останній кадр, LCP і запасний),
pbt-logo-nav.webp (шапка), favicon.png 32 / apple-touch 180 / icon-512, og-pbt.jpg 1200×630."""
import os, subprocess, sys, tempfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'references' / 'brand' / 'logo-anim.mp4'
OUT = ROOT / 'web' / 'media' / 'logo'
W, H, PLATE = 1436, 726, 20
KEEP_CRM = os.environ.get('KEEP_CRM') == '1'
BOX = (240, 120, 1320, 516) if not KEEP_CRM else (240, 120, 1320, 580)   # x0, y0, x1, y1: літери + спалах над T
SKY_TOP, SKY_BOT = (0x1A, 0x87, 0xF5), (0xAA, 0xE4, 0xFC)                # палітра сайту (небо)


def frames():
    if not SRC.exists():
        sys.exit(f'немає {SRC} — скопіювати з ~/Downloads/PBT_CRM_логотип_показ')
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(SRC), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    n = W * H * 3
    while (b := p.stdout.read(n)) and len(b) == n:
        yield np.frombuffer(b, np.uint8).reshape(H, W, 3).astype(np.float32)
    p.wait()


def key(f, plate):
    d = np.abs(f - plate).max(2)
    t = np.clip((d - 20) / 40, 0, 1)                                          # нижче 20 — шум і м'яке сяйво оригіналу (давало синій ореол)
    a = t * t * (3 - 2 * t)                                                   # smoothstep: м'який край без ступенів
    if not KEEP_CRM:
        a[478:, 465:] = 0                                                     # CRM праворуч від гусениці P
        a[506:, :] = 0                                                        # відблиск під літерами
    am = np.maximum(a, 1e-3)[..., None]
    c = np.clip((f - (1 - a[..., None]) * plate) / am, 0, 255)
    edge = (a < .6)[..., None]                                                # despill: на напівпрозорому краї синій не вище за середнє R/G
    c = np.where(edge, np.concatenate([c[..., :2], np.minimum(c[..., 2:], c[..., :2].mean(2, keepdims=True))], 2), c)
    x0, y0, x1, y1 = BOX
    return np.dstack([c, a[..., None] * 255])[y0:y1, x0:x1].round().astype(np.uint8)


def sky(w, h):
    t = np.linspace(0, 1, h)[:, None, None]
    g = (1 - t) * np.array(SKY_TOP) + t * np.array(SKY_BOT)
    return Image.fromarray(np.broadcast_to(g, (h, w, 3)).astype(np.uint8))


def on_sky(logo, w, h, scale):
    bg = sky(w, h).convert('RGBA')
    lw = int(w * scale); lg = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
    bg.alpha_composite(lg, ((w - lg.width) // 2, (h - lg.height) // 2))
    return bg.convert('RGB')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    all_f = list(frames())
    plate = all_f[PLATE]
    with tempfile.TemporaryDirectory() as td:
        for i, f in enumerate(all_f):
            Image.fromarray(key(f, plate), 'RGBA').save(f'{td}/{i:04d}.png')
        last = Image.open(f'{td}/{len(all_f) - 1:04d}.png')
        # VP9 з альфою: Chrome/Edge/Firefox/Android; Safari альфу VP9 не показує — там лишається статичний кадр (site.js)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', '89/3', '-i', f'{td}/%04d.png', '-vf', 'scale=720:-2:flags=lanczos',
                        '-c:v', 'libvpx-vp9', '-pix_fmt', 'yuva420p', '-b:v', '0', '-crf', '38', '-auto-alt-ref', '0', '-row-mt', '1',
                        '-threads', '4', '-an', str(OUT / 'pbt-logo.webm')], check=True)
    lw = last.resize((960, round(last.height * 960 / last.width)), Image.LANCZOS)
    lw.save(OUT / 'pbt-logo.webp', 'WEBP', quality=90, method=6)
    lw.save(OUT / 'pbt-logo.png', optimize=True)
    nav = last.resize((168, round(last.height * 168 / last.width)), Image.LANCZOS)
    nav.save(OUT / 'pbt-logo-nav.webp', 'WEBP', quality=92, method=6)
    for size, name in ((32, 'favicon.png'), (180, 'apple-touch-icon.png'), (512, 'icon-512.png')):
        on_sky(last, size, size, .9).save(OUT / name, optimize=True)
    on_sky(last, 1200, 630, .62).save(OUT / 'og-pbt.jpg', quality=88)
    for p in sorted(OUT.glob('pbt-logo*')) + [OUT / 'og-pbt.jpg', OUT / 'favicon.png']:
        print(p.name, round(p.stat().st_size / 1024), 'КБ')


if __name__ == '__main__':
    main()
