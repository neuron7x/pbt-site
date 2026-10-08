#!/usr/bin/env python3
"""Відео сайту з канонічних кліпів клієнта (TikTok @poltavabudtehnika) — детерміновано, лише ffmpeg.
references/ (не версіюється; імена → docs/PROVENANCE.md):
  compilation.mp4 = 7589580903878380856   hyundai.mp4 = 7587032869399301432   sunset.mp4 = 7688658909661334805
  amph3.mp4 = 7625991020492098837 (три смуги)  longreach.mp4 = 7579201889854606604   trailer.mp4 = 7638993833958722837
  night.mp4 = 7600714811185401108   winter.mp4 = 7588156683126459659   snowjcb.mp4 = 7604826347097050375
Вихід: web/media/video/<name>.mp4 + .webm + .webp (постер). Усі кадри вихідні 576×1024; кропи прибирають накладені написи.
Якщо є references/sr/<name>.mp4 (tools/sr.py, Real-ESRGAN ×2) — беремо його, кропи множимо на 2: смуга 576×324 стає 1152×648
справжніх пікселів замість апскейлу 2,2× у браузері."""
import subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / 'references'
OUT = ROOT / 'web' / 'media' / 'video'
OUT.mkdir(parents=True, exist_ok=True)
X264 = ['-c:v', 'libx264', '-preset', 'slow', '-tune', 'film', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', '-r', '30']
VP9 = ['-c:v', 'libvpx-vp9', '-row-mt', '1', '-tile-columns', '2', '-an', '-r', '30']


def src(name):
    """(шлях, множник кропу): SR-версія ×2, якщо є, інакше оригінал."""
    sr = REF / 'sr' / f'{name}.mp4'
    if sr.exists():
        return str(sr), 2
    p = REF / f'{name}.mp4'
    if not p.exists():
        sys.exit(f'немає {p} — див. docs/PROVENANCE.md')
    return str(p), 1


def k_crop(crop, k):
    return ':'.join(str(int(v) * k) for v in crop.split(':'))


LUT = ROOT / 'config' / 'pbt-look.cube'   # tools/lut.py; після SR кадри чисті — look на 90 % (було 75 % через блоковий шум)
GRADE = ('normalize=blackpt=black:whitept=white:smoothing=24:independence=0:strength=0.5,split[a][b];'
         f'[b]lut3d=file={LUT}:interp=tetrahedral[g];[a][g]blend=all_mode=normal:all_opacity=0.9,hqdn3d=0.8:0.8:2:2,unsharp=13:13:0.30:5:5:0,cas=0.25')


def seg(name, ss, to, vf, out):
    path, _ = src(name)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-threads', '4', '-ss', str(ss), '-to', str(to), '-i', path,
                    '-filter_complex', f'{vf},{GRADE}', *X264, '-crf', '14', str(out)], check=True)


def build(name, parts, scale, cap):
    """parts: [(джерело, від, до, crop у пікселях оригіналу)] → склейка → mp4 + webm + постер; cap — стеля бітрейту, Мбіт/с."""
    with tempfile.TemporaryDirectory() as td:
        lst = Path(td) / 'list.txt'
        lines = []
        for i, (s, a, b, crop) in enumerate(parts):
            f = Path(td) / f'{i:02d}.mp4'
            seg(s, a, b, f'crop={k_crop(crop, src(s)[1])},scale={scale}:flags=lanczos,setsar=1', f)
            lines.append(f"file '{f}'")
        lst.write_text('\n'.join(lines))
        base = ['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst)]
        subprocess.run(base + X264 + ['-crf', '21', '-maxrate', f'{cap}M', '-bufsize', f'{cap * 2}M', str(OUT / f'{name}.mp4')], check=True)
        subprocess.run(base + VP9 + ['-crf', '30', '-b:v', f'{cap * 0.75:.2f}M', str(OUT / f'{name}.webm')], check=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '0.4', '-i', str(OUT / f'{name}.mp4'), '-frames:v', '1', '-c:v', 'libwebp', '-quality', '80', str(OUT / f'{name}.webp')], check=True)
    sizes = {ext: round((OUT / f'{name}.{ext}').stat().st_size / 1024) for ext in ('mp4', 'webm', 'webp')}
    print(name, sizes)


W = '576:324:0:350'            # ландшафтна смуга з портретного кадру
HERO = [('compilation', 3.0, 5.8, None), ('compilation', 36.0, 39.5, None), ('compilation', 27.0, 29.0, None), ('compilation', 12.0, 14.5, None),
        ('sunset', 6.0, 9.0, None), ('hyundai', 4.0, 7.0, None)]
build('hero-wide', [(s, a, b, W if s != 'hyundai' else '576:324:0:330') for s, a, b, _ in HERO], '1920:1080', 4.5)
build('hero-wide-720', [(s, a, b, W if s != 'hyundai' else '576:324:0:330') for s, a, b, _ in HERO], '1280:720', 2.2)   # легка версія: звичайні екрани, повільна мережа, однофайлова збірка
build('hero-tall', [(s, a, b, '576:1024:0:0' if s != 'hyundai' else '576:776:0:64') for s, a, b, _ in HERO], '720:1280', 3)

JOB, J = '960:540', 1.6
build('job-voda', [('compilation', 36.0, 40.0, W)], JOB, J)
build('job-zemlia', [('snowjcb', 2.0, 8.0, '498:280:39:240')], JOB, J)
build('job-trans', [('trailer', 12.0, 17.0, '576:324:0:180')], JOB, J)
build('job-lis', [('compilation', 12.0, 14.5, W), ('compilation', 16.0, 18.0, W)], JOB, J)
build('job-demont', [('compilation', 3.0, 9.0, '576:324:0:300')], JOB, J)

build('proof-amph', [('amph3', 0.5, 6.5, '552:310:12:340')], JOB, J)
build('proof-long', [('longreach', 2.0, 8.0, '480:270:48:322')], JOB, J)
build('proof-trailer', [('trailer', 2.0, 8.0, '576:324:0:180')], JOB, J)
build('proof-night', [('night', 2.0, 8.0, '480:270:48:352')], JOB, J)
build('proof-winter', [('winter', 1.0, 7.0, '480:270:48:268')], JOB, J)
build('proof-sunset', [('sunset', 2.0, 8.0, '576:324:0:330')], JOB, J)
print('→', OUT, 'разом КБ:', round(sum(f.stat().st_size for f in OUT.iterdir()) / 1024))
