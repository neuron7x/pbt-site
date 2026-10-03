#!/usr/bin/env python3
"""Кадри героя з канонічного кліпу (детерміновано): references/hero.mp4 → web/media/hero/f_001..040.webp + poster.webp.
Джерело кліпу: TikTok @poltavabudtehnika/video/7587032869399301432 (власна зйомка клієнта), 576×1024, 11.8 с;
кроп 576×776 від y=64 прибирає логотип угорі й накладений текст унизу.
Вимоги: ffmpeg, Pillow. references/ не версіюється — кадри в web/media/hero версіюються як результат."""
import glob, os, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'references' / 'hero.mp4'
OUT = ROOT / 'web' / 'media' / 'hero'
N, W, H, Q = 40, 540, 728, 68
START, LEN = 0.6, 10.0          # без чорного входу/виходу кліпу (0–0.5 с і 10.8–11.8 с)
if not SRC.exists():
    sys.exit(f'немає {SRC}: поклади канонічний кліп (див. docs/PROVENANCE.md)')
dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(SRC)]).decode().strip())
with tempfile.TemporaryDirectory() as td:
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(START), '-t', str(LEN), '-i', str(SRC), '-vf', f'fps={N}/{LEN:.3f},crop=576:776:0:64,scale={W}:{H}', f'{td}/%03d.png'], check=True)
    pngs = sorted(glob.glob(f'{td}/*.png'))[:N]
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob('f_*.webp'):
        f.unlink()
    for k, p in enumerate(pngs, 1):
        Image.open(p).convert('RGB').save(OUT / f'f_{k:03d}.webp', 'WEBP', quality=Q, method=6)
    Image.open(pngs[0]).convert('RGB').save(OUT / 'poster.webp', 'WEBP', quality=78, method=6)
print(f'{len(pngs)} кадрів → {OUT}')
