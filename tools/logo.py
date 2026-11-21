#!/usr/bin/env python3
"""Build the user-authorized ПЛЕЙНБУД wordmark from local font and geometry.

Run: python3 tools/logo.py
Uses the existing Pillow/numpy environment and ffmpeg/libvpx-vp9; no network or
private source footage. Preserves the blue/gold palette, image geometry, and
one-shot transparent VP9/static fallback contract. This is a newly generated
brand treatment, with no claim of official registered-logo status.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont, __version__ as pillow_version

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'web/media/logo'
FONT = ROOT / 'web/fonts/IBMPlexSans-600-cyrillic.woff2'
WORDMARK = 'ПЛЕЙНБУД'
HERO_SIZE, NAV_SIZE, VIDEO_SIZE = (960, 352), (168, 62), (720, 264)
FRAMES, FPS, SCALE = 159, '89/3', 3
BLUE, INK, GOLD, PAPER = (26, 135, 245), (6, 43, 92), (253, 197, 1), (245, 245, 242)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def geometric_mark(size, antialias=SCALE):
    """One structural П; no excavator, crane, hooks or inherited PBT initials."""
    image = Image.new('RGBA', (size * antialias, size * antialias))
    draw = ImageDraw.Draw(image)
    unit = size * antialias / 100
    def polygon(points, fill):
        draw.polygon([(round(x * unit), round(y * unit)) for x, y in points], fill=fill)
    polygon([(10, 12), (90, 12), (90, 88), (70, 88), (70, 32), (30, 32), (30, 88), (10, 88)], (*INK, 255))
    polygon([(13, 15), (87, 15), (87, 85), (73, 85), (73, 29), (27, 29), (27, 85), (13, 85)], (*GOLD, 255))
    draw.rectangle((round(34 * unit), round(76 * unit), round(66 * unit), round(85 * unit)), fill=(*BLUE, 255))
    return image.resize((size, size), Image.Resampling.LANCZOS)


def full_brand_wordmark():
    """Full mark and wordmark composition for the large sharing card."""
    image = Image.new('RGBA', (HERO_SIZE[0] * SCALE, HERO_SIZE[1] * SCALE))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(FONT), 135 * SCALE)
    bounds = draw.textbbox((0, 0), WORDMARK, font=font)
    tw, th = bounds[2] - bounds[0], bounds[3] - bounds[1]
    mark_size, gap = 146 * SCALE, 22 * SCALE
    left = (image.width - mark_size - gap - tw) // 2
    image.alpha_composite(geometric_mark(mark_size, 1), (left, (image.height - mark_size) // 2))
    draw.text((left + mark_size + gap - bounds[0], (image.height - th) // 2 - bounds[1]),
              WORDMARK, font=font, fill=(*PAPER, 255), stroke_width=2 * SCALE, stroke_fill=(*INK, 255))
    return image.resize(HERO_SIZE, Image.Resampling.LANCZOS)


def hero_wordmark():
    """Compact wordmark for the unchanged 96/80px hero slot.

    Optical horizontal condensation preserves roughly 15px cap height at the
    96px display width. There is no separate symbol taking width from the name.
    """
    font = ImageFont.truetype(str(FONT), 220 * SCALE)
    stroke = 2 * SCALE
    bounds = font.getbbox(WORDMARK)
    letters = Image.new('RGBA', (bounds[2] - bounds[0] + 2 * stroke,
                                 bounds[3] - bounds[1] + 2 * stroke))
    ImageDraw.Draw(letters).text((stroke - bounds[0], stroke - bounds[1]), WORDMARK,
                                font=font, fill=(*PAPER, 255),
                                stroke_width=stroke, stroke_fill=(*INK, 255))
    letters = letters.resize((944 * SCALE, letters.height), Image.Resampling.LANCZOS)
    image = Image.new('RGBA', (HERO_SIZE[0] * SCALE, HERO_SIZE[1] * SCALE))
    image.alpha_composite(letters, ((image.width - letters.width) // 2,
                                    (image.height - letters.height) // 2))
    return image.resize(HERO_SIZE, Image.Resampling.LANCZOS)


def sky(size):
    w, h = size
    t = np.linspace(0, 1, h)[:, None, None]
    gradient = np.broadcast_to((1 - t) * np.array(BLUE) + t * np.array((170, 228, 252)), (h, w, 3))
    return Image.fromarray(np.rint(gradient).astype(np.uint8)).convert('RGBA')


def square_icon(size):
    image = sky((size, size))
    mark = geometric_mark(round(size * .82))
    image.alpha_composite(mark, ((size - mark.width) // 2, (size - mark.height) // 2))
    return image.convert('RGB')


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
    logo = hero_wordmark()
    logo.save(OUT / 'plainbud-logo.png', optimize=True)
    logo.save(OUT / 'plainbud-logo.webp', 'WEBP', lossless=True, method=6, exact=True)
    # The text name is hidden by the existing narrow-mobile navigation CSS.
    # Keep the complete wordmark legible in that existing 70/84px-wide slot.
    nav = Image.new('RGBA', (NAV_SIZE[0] * SCALE, NAV_SIZE[1] * SCALE))
    nd = ImageDraw.Draw(nav)
    nf = ImageFont.truetype(str(FONT), 30 * SCALE)
    nb = nd.textbbox((0, 0), WORDMARK, font=nf)
    nd.text(((nav.width - nb[2] + nb[0]) // 2 - nb[0],
             (nav.height - nb[3] + nb[1]) // 2 - nb[1]), WORDMARK, font=nf,
            fill=(*GOLD, 255), stroke_width=SCALE, stroke_fill=(*INK, 255))
    nav = nav.resize(NAV_SIZE, Image.Resampling.LANCZOS)
    nav.save(OUT / 'plainbud-logo-nav.webp', 'WEBP', lossless=True, method=6, exact=True)
    for size, name in ((32, 'favicon.png'), (180, 'apple-touch-icon.png'), (512, 'icon-512.png')):
        square_icon(size).save(OUT / name, optimize=True)
    og = sky((1200, 630))
    full_brand = full_brand_wordmark()
    og.alpha_composite(full_brand, ((og.width - full_brand.width) // 2,
                                    (og.height - full_brand.height) // 2))
    og.convert('RGB').save(OUT / 'og-plainbud.jpg', quality=92, subsampling=0, optimize=True)
    with tempfile.TemporaryDirectory(prefix='plainbud-brand-') as folder:
        temp = Path(folder)
        video = np.array(logo.resize(VIDEO_SIZE, Image.Resampling.LANCZOS))
        for i in range(FRAMES):
            animation_frame(video, i).save(temp / f'{i:04d}.png')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-fflags', '+bitexact', '-framerate', FPS,
                        '-i', str(temp / '%04d.png'), '-c:v', 'libvpx-vp9', '-pix_fmt', 'yuva420p',
                        '-b:v', '0', '-crf', '28', '-auto-alt-ref', '0', '-row-mt', '0', '-threads', '1',
                        '-g', str(FRAMES), '-flags:v', '+bitexact', '-map_metadata', '-1', '-an',
                        '-fflags', '+bitexact',
                        str(OUT / 'plainbud-logo.webm')], check=True)
    names = ['plainbud-logo.png', 'plainbud-logo.webp', 'plainbud-logo-nav.webp', 'plainbud-logo.webm',
             'favicon.png', 'apple-touch-icon.png', 'icon-512.png', 'og-plainbud.jpg']
    outputs = {}
    for name in names:
        path = OUT / name
        item = {'sha256': digest(path), 'bytes': path.stat().st_size}
        if path.suffix != '.webm':
            with Image.open(path) as image:
                item.update(width=image.width, height=image.height, mode=image.mode)
        else:
            item.update(width=VIDEO_SIZE[0], height=VIDEO_SIZE[1], frames=FRAMES, fps=FPS,
                        alpha=True, playback='once; static first/last frame')
        outputs[name] = item
    manifest = {'schema': 'plainbud-brand-assets-v1', 'brand': WORDMARK,
                'status': 'User-authorized generated wordmark; no official trademark status asserted',
                'generation_command': 'python3 tools/logo.py', 'generator_sha256': digest(__file__),
                'font': {'path': str(FONT.relative_to(ROOT)), 'sha256': digest(FONT)},
                'toolchain': {'pillow': pillow_version, 'numpy': np.__version__,
                              'ffmpeg': subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0]},
                'palette': {'blue': '#1A87F5', 'ink': '#062B5C', 'gold': '#FDC501', 'paper': '#F5F5F2'},
                'outputs': outputs}
    (OUT / 'plainbud-brand-manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
