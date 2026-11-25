#!/usr/bin/env python3
"""Відео сайту з канонічних кліпів клієнта (TikTok @poltavabudtehnika) — детерміновано, лише ffmpeg.
references/ (не версіюється; імена → docs/PROVENANCE.md):
  compilation.mp4 = 7589580903878380856   hyundai.mp4 = 7587032869399301432   sunset.mp4 = 7688658909661334805
  amph3.mp4 = 7625991020492098837 (три смуги)  longreach.mp4 = 7579201889854606604   trailer.mp4 = 7638993833958722837
  night.mp4 = 7600714811185401108   winter.mp4 = 7588156683126459659   snowjcb.mp4 = 7604826347097050375
Вихід: web/media/video/<name>.mp4 + .webm + .webp (постер).
Кодування (25.11.2026): шматки — проміжні без втрат (qp 0), тож фінальний файл має одне покоління втрат, а не два;
H.264 і VP9 — у два проходи на цільовому бітрейті. Вимір на hero-wide проти еталона без втрат, той самий розмір:
VP9 36,55 → 37,60 дБ PSNR (SSIM 0,9623 → 0,9697), H.264 36,31 → 36,72 дБ (SSIM 0,9667 → 0,9688). docs/PROVENANCE.md. Усі кадри вихідні 576×1024; кропи прибирають накладені написи.
Якщо є references/sr/<name>.mp4 (tools/sr.py, Real-ESRGAN ×2) — беремо його, кропи множимо на 2.
SR не відновлює доказово справжні деталі; розмір виходу не є роздільністю оригінальної зйомки."""
import argparse
import subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / 'references'
OUT = ROOT / 'web' / 'media' / 'video'
X264 = ['-c:v', 'libx264', '-threads', '2', '-preset', 'slow', '-tune', 'film', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', '-r', '30']
VP9 = ['-c:v', 'libvpx-vp9', '-threads', '2', '-row-mt', '1', '-tile-columns', '2', '-an', '-r', '30']


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
         f'[b]lut3d=file={LUT}:interp=tetrahedral[g];[a][g]blend=all_mode=normal:all_opacity=0.9,hqdn3d=0.8:0.8:2:2,unsharp=13:13:0.18:5:5:0')   # SR вже дає край; cas + clarity 0.30 давали ореоли й «акварель» (огляд 08.10)


def seg(name, ss, to, vf, out):
    path, _ = src(name)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-threads', '2', '-filter_complex_threads', '1', '-ss', str(ss), '-to', str(to), '-i', path,
                    '-filter_complex', f'{vf},{GRADE}', '-c:v', 'libx264', '-threads', '2', '-preset', 'ultrafast', '-qp', '0',
                    '-pix_fmt', 'yuv420p', '-an', '-r', '30', str(out)], check=True)   # проміжний без втрат


def poster(name):
    """Амфібія в герої замість першого кадру з демонтованим дахом."""
    timestamp = HERO_POSTER_TIME if name.startswith('hero-') else 0.4
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-threads', '1', '-ss', str(timestamp),
                    '-i', str(OUT / f'{name}.mp4'), '-frames:v', '1', '-threads', '1',
                    '-c:v', 'libwebp', '-quality', '80', str(OUT / f'{name}.webp')], check=True)


def build(name, parts, scale, cap):
    """parts: [(джерело, від, до, crop у пікселях оригіналу)] → склейка → mp4 + webm + постер; cap — стеля бітрейту, Мбіт/с."""
    with tempfile.TemporaryDirectory(prefix='pbt-site-media-') as td:
        lst = Path(td) / 'list.txt'
        lines = []
        for i, (s, a, b, crop) in enumerate(parts):
            f = Path(td) / f'{i:02d}.mp4'
            seg(s, a, b, f'crop={k_crop(crop, src(s)[1])},scale={scale}:flags=lanczos,setsar=1', f)
            lines.append(f"file '{f}'")
        lst.write_text('\n'.join(lines))
        base = ['ffmpeg', '-v', 'error', '-y', '-threads', '2', '-f', 'concat', '-safe', '0', '-i', str(lst)]
        kh, kv = TARGET_KBPS.get(name, (round(cap * 970), round(cap * 740)))
        h264 = base + X264 + ['-b:v', f'{kh}k', '-maxrate', f'{round(kh * 1.65)}k', '-bufsize', f'{kh * 3}k', '-passlogfile', str(Path(td) / 'x264')]
        subprocess.run(h264 + ['-pass', '1', '-f', 'null', '/dev/null'], check=True)
        subprocess.run(h264 + ['-pass', '2', str(OUT / f'{name}.mp4')], check=True)
        vp9 = base + VP9 + ['-deadline', 'good', '-cpu-used', '1', '-auto-alt-ref', '1', '-lag-in-frames', '25', '-b:v', f'{kv}k',
                            '-passlogfile', str(Path(td) / 'vp9')]
        subprocess.run(vp9 + ['-pass', '1', '-f', 'null', '/dev/null'], check=True)
        subprocess.run(vp9 + ['-pass', '2', str(OUT / f'{name}.webm')], check=True)
        if POSTERS:
            poster(name)
    sizes = {ext: round((OUT / f'{name}.{ext}').stat().st_size / 1024) for ext in ('mp4', 'webm', 'webp') if (OUT / f'{name}.{ext}').exists()}
    print(name, sizes)


W = '576:324:0:350'            # ландшафтна смуга з портретного кадру
HERO_POSTER_TIME = 7.2
# Межі перевірено на оригіналі 576×1024: sunset має чорні рядки 0–128 і 894–1023.
# Вікно sunset точно 9:16; воно не розтягує зображення й не включає чорні смуги.
HERO_TALL_CROPS = {'sunset': '414:736:80:144', 'hyundai': '432:768:32:64'}
# Середня панель amph3 займає y=353…669; старий y=340 захоплював сусідню панель.
PROOF_AMPH_CROP = '552:310:12:356'
HERO = [('compilation', 3.0, 5.8, None), ('compilation', 36.0, 39.5, None), ('compilation', 27.0, 29.0, None), ('compilation', 12.0, 14.5, None),
        ('sunset', 6.0, 9.0, None), ('hyundai', 4.0, 7.0, None)]
JOB, J = '960:540', 1.6
BUILDS = {
    'hero-wide': ([(s, a, b, W if s != 'hyundai' else '576:324:0:330') for s, a, b, _ in HERO], '1920:1080', 4.5),
    'hero-wide-720': ([(s, a, b, W if s != 'hyundai' else '576:324:0:330') for s, a, b, _ in HERO], '1280:720', 2.2),
    'hero-tall': ([(s, a, b, HERO_TALL_CROPS.get(s, '576:1024:0:0')) for s, a, b, _ in HERO], '720:1280', 3),
    'job-voda': ([('compilation', 36.0, 40.0, W)], JOB, J),
    'job-zemlia': ([('snowjcb', 2.0, 8.0, '498:280:39:240')], JOB, J),
    'job-trans': ([('trailer', 12.0, 17.0, '576:324:0:180')], JOB, J),
    'job-lis': ([('compilation', 12.0, 14.5, W), ('compilation', 16.0, 18.0, W)], JOB, J),
    'job-demont': ([('compilation', 3.0, 9.0, '576:324:0:300')], JOB, J),
    'proof-amph': ([('amph3', 0.5, 6.5, PROOF_AMPH_CROP)], JOB, J),
    'proof-long': ([('longreach', 2.0, 8.0, '480:270:48:350')], JOB, J),
    'proof-trailer': ([('trailer', 2.0, 8.0, '576:324:0:180')], JOB, J),
    'proof-night': ([('night', 2.0, 8.0, '480:270:48:352')], JOB, J),
    'proof-winter': ([('winter', 1.0, 7.0, '480:270:48:352')], JOB, J),
    'proof-sunset': ([('sunset', 2.0, 8.0, '576:324:0:330')], JOB, J),
}


POSTERS = True
# цільовий бітрейт (кбіт/с) = розмір попереднього файлу: якість порівнюється на тому самому бюджеті ваги
TARGET_KBPS = {'hero-tall': (2741, 2430), 'job-voda': (1815, 1370), 'job-zemlia': (1747, 1588), 'job-lis': (1722, 1812), 'job-demont': (1648, 1426), 'proof-amph': (1760, 1419), 'proof-long': (1707, 1149), 'proof-night': (1239, 745), 'proof-winter': (1606, 1583), 'proof-sunset': (526, 634)}


def main():
    global REF, OUT, POSTERS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-dir', type=Path, default=REF, help='тека вихідних кліпів, лише читання')
    parser.add_argument('--only', nargs='+', choices=BUILDS, help='генерувати лише названі кліпи')
    parser.add_argument('--out-dir', type=Path, default=OUT, help='куди писати (за замовчуванням web/media/video)')
    parser.add_argument('--no-posters', action='store_true', help='не перезаписувати постери .webp (їхні sha256 закріплено)')
    parser.add_argument('--posters-only', action='store_true', help='постери з готових mp4 без перекодування відео')
    args = parser.parse_args()
    REF = args.reference_dir.resolve()
    OUT = args.out_dir.resolve()
    POSTERS = not args.no_posters
    OUT.mkdir(parents=True, exist_ok=True)
    for name in args.only or BUILDS:
        if args.posters_only:
            poster(name)
        else:
            build(name, *BUILDS[name])
    print('→', OUT, 'разом КБ:', round(sum(f.stat().st_size for f in OUT.iterdir()) / 1024))


if __name__ == '__main__':
    main()
