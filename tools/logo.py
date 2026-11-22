#!/usr/bin/env python3
"""Build the ПЛЕЙНБУД identity: custom stencil wordmark + chamfered П monogram.

Run: python3 tools/logo.py
Geometry comes from the site's own display face (web/fonts/Tektur-var-cyrillic.woff2,
SIL OFL 1.1), instanced at wght 900 with fontTools and then customised:
  * Й carries a chamfered gold bar instead of the stock breve;
  * one horizontal stencil cut runs through every letter (industrial marking);
  * tracking is tightened to a single solid block.
The monogram is drawn from first principles: a chamfered ink tile, a gold П with
the same 45° cut corners as Tektur and the same stencil slot, and a blue base bar.
Vector sources are written next to the rasters (SVG) so the mark scales cleanly.
Rendering: cairosvg (vector → raster), Pillow (encode), ffmpeg/libvpx-vp9 (one-shot
transparent sweep). No network, no stock artwork, no claim of trademark status.
"""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile

import cairosvg
import fontTools
import numpy as np
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image, __version__ as pillow_version

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'web/media/logo'
FONT = ROOT / 'web/fonts/Tektur-var-cyrillic.woff2'
WORDMARK = 'ПЛЕЙНБУД'
HERO_SIZE, VIDEO_SIZE = (960, 352), (720, 264)
NAV_HEIGHT = 62                      # 2× of the 31 px CSS slot
FRAMES, FPS = 159, '89/3'
BLUE, INK, GOLD, PAPER = '#1A87F5', '#062B5C', '#FDC501', '#F5F5F2'
INK_RGB, DEEP_RGB = (6, 43, 92), (10, 70, 150)

# Font units (UPM 1000, cap height 700).
TRACK = -10
CAP = 700
SLOT_Y, SLOT_H = 0.40 * CAP, 34      # stencil cut: centre height above baseline, thickness
OUTLINE = 26                         # side padding; an ink keyline exists but is off: on light grounds it
                                     # turned the stencil cut into a strike-through
TOP, BOTTOM = 900, 260               # room for the Й bar above cap and Д descender below baseline


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _font():
    return instantiateVariableFont(TTFont(FONT), {'wght': 900})


def wordmark_paths():
    """Return (svg path elements in font units, y-up), total advance width."""
    font = _font()
    glyphs, cmap, hmtx = font.getGlyphSet(), font.getBestCmap(), font['hmtx']
    x, parts = 0, []
    for ch in WORDMARK:
        name = cmap[ord('И' if ch == 'Й' else ch)]
        pen, box = SVGPathPen(glyphs), BoundsPen(glyphs)
        glyphs[name].draw(pen)
        glyphs[name].draw(box)
        parts.append(f'<path transform="translate({x},0)" d="{pen.getCommands()}"/>')
        if ch == 'Й':
            xmin, _, xmax, top = box.bounds
            c = x + (xmin + xmax) / 2
            parts.append(f'<path d="M{c - 150},{top + 70} L{c + 170},{top + 70} '
                         f'L{c + 130},{top + 150} L{c - 190},{top + 150}Z"/>')
        x += hmtx[name][0] + TRACK
    return ''.join(parts), x - TRACK


def wordmark_group(paths, width, keyline=False, fill=GOLD):
    """Stencil-cut gold wordmark in a box (0..width+2·OUTLINE, 0..TOP+BOTTOM), y-down."""
    w, h = width + 2 * OUTLINE, TOP + BOTTOM
    base = TOP
    cut = base - SLOT_Y - SLOT_H / 2
    clip = (f'<clipPath id="stencil"><rect x="-1" y="-1" width="{w + 2}" height="{cut + 1}"/>'
            f'<rect x="-1" y="{cut + SLOT_H}" width="{w + 2}" height="{h - cut - SLOT_H + 1}"/></clipPath>')
    glyph = f'transform="translate({OUTLINE},{base}) scale(1,-1)"'
    inner = ''
    if keyline:
        inner += (f'<g {glyph} fill="{INK}" stroke="{INK}" stroke-width="{2 * OUTLINE}" '
                  f'stroke-linejoin="miter">{paths}</g>')
    inner += f'<g {glyph} fill="{fill}">{paths}</g>'
    return clip, f'<g clip-path="url(#stencil)">{inner}</g>', (w, h)


def mark_svg_body(u):
    """Monogram on a 100u square."""
    tile = f'M{6*u},0 L{100*u},0 L{100*u},{94*u} L{94*u},{100*u} L0,{100*u} L0,{6*u}Z'
    p = (f'M{22*u},{22*u} L{72*u},{22*u} L{80*u},{30*u} L{80*u},{76*u} L{63*u},{76*u} L{63*u},{39*u} '
         f'L{37*u},{39*u} L{37*u},{76*u} L{20*u},{76*u} L{20*u},{24*u}Z')
    return (f'<path d="{tile}" fill="{INK}"/><path d="{p}" fill="{GOLD}"/>'
            f'<rect x="0" y="{54*u}" width="{100*u}" height="{4*u}" fill="{INK}"/>'
            f'<path d="M{20*u},{83*u} L{80*u},{83*u} L{77*u},{88*u} L{20*u},{88*u}Z" fill="{BLUE}"/>')


def svg(w, h, body, defs=''):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
            f'<defs>{defs}</defs>{body}</svg>')


def wordmark_svg():
    paths, width = wordmark_paths()
    clip, group, (w, h) = wordmark_group(paths, width)
    return svg(w, h, group, clip), (w, h)


def mark_svg():
    return svg(1000, 1000, mark_svg_body(10))


def lockup_svg(fill=GOLD):
    """Monogram + wordmark; wordmark cap height = 50 % of the tile, optically centred."""
    paths, width = wordmark_paths()
    clip, group, (w, h) = wordmark_group(paths, width, fill=fill)
    tile = 1000
    s = (tile * .5) / CAP                       # font units → lockup units
    gap = 0.22 * tile
    cap_top = TOP - CAP                          # cap top inside wordmark box (y-down)
    y = tile / 2 - (cap_top + CAP / 2) * s
    total_w = tile + gap + w * s
    body = mark_svg_body(10) + f'<g transform="translate({tile + gap},{y}) scale({s})">{group}</g>'
    return svg(total_w, tile, body, clip), (total_w, tile)


def render(svg_text, width=None, height=None):
    data = cairosvg.svg2png(bytestring=svg_text.encode(), output_width=width, output_height=height)
    return Image.open(io.BytesIO(data)).convert('RGBA')


def fit_on_canvas(image, size, margin):
    """Scale into size minus margin (px), centred, transparent canvas."""
    w, h = size
    k = min((w - 2 * margin) / image.width, (h - 2 * margin) / image.height)
    scaled = image.resize((round(image.width * k), round(image.height * k)), Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', size)
    canvas.alpha_composite(scaled, ((w - scaled.width) // 2, (h - scaled.height) // 2))
    return canvas


def square_icon(size):
    """Opaque icon: the chamfered tile sits on a full ink square (no black corners)."""
    image = Image.new('RGBA', (size, size), INK)
    image.alpha_composite(render(mark_svg(), size, size))
    return image.convert('RGB')


def night(size):
    """Dark brand ground for the share card: ink at the top → deep blue at the bottom, like the hero."""
    w, h = size
    t = np.linspace(0, 1, h)[:, None, None]
    gradient = np.broadcast_to((1 - t) * np.array(INK_RGB) + t * np.array(DEEP_RGB), (h, w, 3))
    return Image.fromarray(np.rint(gradient).astype(np.uint8)).convert('RGBA')


def animation_frame(base, index):
    """One restrained light sweep; first/last frames equal the static mark."""
    if index in (0, FRAMES - 1):
        return Image.fromarray(base)
    progress = index / (FRAMES - 1)
    strength = .24 * np.sin(np.pi * progress) ** 2
    x = np.arange(base.shape[1], dtype=float)[None, :]
    y = np.arange(base.shape[0], dtype=float)[:, None]
    center = -120 + progress * (base.shape[1] + 240)
    band = np.exp(-((x - center + (y - base.shape[0] / 2) * .24) / 44) ** 2)
    rgba = base.copy()
    rgb = base[:, :, :3].astype(float)
    rgba[:, :, :3] = np.rint(rgb + (255 - rgb) * (band * strength)[:, :, None]).astype(np.uint8)
    return Image.fromarray(rgba)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if not FONT.is_file():
        raise SystemExit(f'Missing versioned font: {FONT.relative_to(ROOT)}')
    wm_svg, (wm_w, wm_h) = wordmark_svg()
    lk_svg, (lk_w, lk_h) = lockup_svg()
    mk_svg = mark_svg()
    (OUT / 'plainbud-wordmark.svg').write_text(wm_svg + '\n', encoding='utf-8')
    (OUT / 'plainbud-lockup.svg').write_text(lk_svg + '\n', encoding='utf-8')
    (OUT / 'plainbud-mark.svg').write_text(mk_svg + '\n', encoding='utf-8')

    # Hero slot (960×352 intrinsic, ~96 px CSS): the wordmark alone, full width.
    hero = fit_on_canvas(render(wm_svg, width=HERO_SIZE[0] * 2), HERO_SIZE, 8)
    hero.save(OUT / 'plainbud-logo.png', optimize=True)
    hero.save(OUT / 'plainbud-logo.webp', 'WEBP', lossless=True, method=6, exact=True)

    # Navigation: one lockup, 31 px tall in CSS. The text name is no longer repeated next to it.
    nav_w = round(lk_w * NAV_HEIGHT / lk_h)
    nav = render(lk_svg, width=nav_w * 2).resize((nav_w, NAV_HEIGHT), Image.Resampling.LANCZOS)
    nav.save(OUT / 'plainbud-logo-nav.webp', 'WEBP', lossless=True, method=6, exact=True)
    # Solid (light) header after scrolling: same lockup with an ink wordmark; gold on white fails contrast.
    ink_svg, _ = lockup_svg(INK)
    ink = render(ink_svg, width=nav_w * 2).resize((nav_w, NAV_HEIGHT), Image.Resampling.LANCZOS)
    ink.save(OUT / 'plainbud-logo-nav-ink.webp', 'WEBP', lossless=True, method=6, exact=True)

    for size, name in ((32, 'favicon.png'), (180, 'apple-touch-icon.png'), (512, 'icon-512.png')):
        square_icon(size).save(OUT / name, optimize=True)

    og = night((1200, 630))
    card = fit_on_canvas(render(lk_svg, width=2000), (1200, 630), 150)
    og.alpha_composite(card)
    og.convert('RGB').save(OUT / 'og-plainbud.jpg', quality=92, subsampling=0, optimize=True)

    with tempfile.TemporaryDirectory(prefix='plainbud-brand-') as folder:
        temp = Path(folder)
        video = np.array(hero.resize(VIDEO_SIZE, Image.Resampling.LANCZOS))
        for i in range(FRAMES):
            animation_frame(video, i).save(temp / f'{i:04d}.png')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-fflags', '+bitexact', '-framerate', FPS,
                        '-i', str(temp / '%04d.png'), '-c:v', 'libvpx-vp9', '-pix_fmt', 'yuva420p',
                        '-b:v', '0', '-crf', '28', '-auto-alt-ref', '0', '-row-mt', '0', '-threads', '1',
                        '-g', str(FRAMES), '-flags:v', '+bitexact', '-map_metadata', '-1', '-an',
                        '-fflags', '+bitexact',
                        str(OUT / 'plainbud-logo.webm')], check=True)

    names = ['plainbud-logo.png', 'plainbud-logo.webp', 'plainbud-logo-nav.webp', 'plainbud-logo-nav-ink.webp',
             'plainbud-logo.webm',
             'favicon.png', 'apple-touch-icon.png', 'icon-512.png', 'og-plainbud.jpg',
             'plainbud-wordmark.svg', 'plainbud-lockup.svg', 'plainbud-mark.svg']
    outputs = {}
    for name in names:
        path = OUT / name
        item = {'sha256': digest(path), 'bytes': path.stat().st_size}
        if path.suffix == '.webm':
            item.update(width=VIDEO_SIZE[0], height=VIDEO_SIZE[1], frames=FRAMES, fps=FPS,
                        alpha=True, playback='once; static first/last frame')
        elif path.suffix != '.svg':
            with Image.open(path) as image:
                item.update(width=image.width, height=image.height, mode=image.mode)
        outputs[name] = item
    manifest = {'schema': 'plainbud-brand-assets-v2', 'brand': WORDMARK,
                'status': 'User-authorized custom wordmark and monogram; no official trademark status asserted',
                'construction': {'wordmark': 'Tektur wght 900 outlines, tracking -10/1000, custom Й bar, '
                                             'transparent stencil cut at 40 % cap height',
                                 'monogram': 'chamfered ink tile, gold П with 45° corners and matching '
                                             'stencil slot, blue base bar'},
                'generation_command': 'python3 tools/logo.py', 'generator_sha256': digest(__file__),
                'font': {'path': str(FONT.relative_to(ROOT)), 'sha256': digest(FONT), 'license': 'SIL OFL 1.1'},
                'toolchain': {'pillow': pillow_version, 'numpy': np.__version__,
                              'fonttools': fontTools.version, 'cairosvg': cairosvg.__version__,
                              'ffmpeg': subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0]},
                'palette': {'blue': BLUE, 'ink': INK, 'gold': GOLD, 'paper': PAPER},
                'outputs': outputs}
    (OUT / 'plainbud-brand-manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'nav': [nav_w, NAV_HEIGHT], 'wordmark_units': [wm_w, wm_h]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
