#!/usr/bin/env python3
"""Секція «Масштаб»: ілюстративні кліпи з Wikimedia Commons (config/stock.json) — детерміновано, лише ffmpeg.
Fail-closed: ліцензія поза allowed_licenses, відсутній файл або sha256 ≠ маніфесту — вихід із кодом 1, нічого не пишемо.
Вихід web/media/cine/<id>-w.{mp4,webm,webp} (1920×1080) і <id>-m.{mp4,webm,webp} (720×1280, кроп за focus).
Грейд зводить різну зйомку до палітри «Небо і золото»: холодні тіні, теплі світла, м'яка віньєтка."""
import hashlib, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / 'config' / 'stock.json').read_text(encoding='utf-8'))
REF = ROOT / 'references' / 'stock'
OUT = ROOT / 'web' / 'media' / 'cine'
LUT = ROOT / 'config' / 'pbt-look.cube'   # tools/lut.py: look «Небо і золото» (S-крива, тонування чорнило/золото, вібранс, небо/фарба)
GRADE = ('normalize=blackpt=black:whitept=white:smoothing=24:independence=0:strength=0.5,'   # вирівняти експозицію й баланс різних камер
         f'lut3d=file={LUT}:interp=tetrahedral,'
         'hqdn3d=1.2:1.2:2.5:2.5,unsharp=13:13:0.30:5:5:0,cas=0.35,vignette=angle=PI/6')                              # шум геть до стиснення → менше бітів на зерно
X264 = ['-c:v', 'libx264', '-preset', 'slow', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', '-r', '30']
VP9 = ['-c:v', 'libvpx-vp9', '-row-mt', '1', '-tile-columns', '2', '-an', '-r', '30']   # -threads 4: машина спільна з CRM, 16 потоків → OOM (137)
FADE = 0.35   # з/до чорного на межі петлі — шов не видно


def check():
    errs = []
    for key, s in CFG['sources'].items():
        if s['license'] not in CFG['allowed_licenses']:
            errs.append(f'{key}: ліцензія {s["license"]} не дозволена')
        f = REF / s['file']
        if not f.exists():
            errs.append(f'{key}: немає {f} — завантажити з {s["page"]}')
        elif hashlib.sha256(f.read_bytes()).hexdigest() != s['sha256']:
            errs.append(f'{key}: sha256 не збігається з маніфестом')
    for c in CFG['chapters']:
        if c['source'] not in CFG['sources']:
            errs.append(f'{c["id"]}: невідоме джерело {c["source"]}')
    if errs:
        sys.exit('\n'.join(errs))


def encode(src, a, b, vf, out, crf_h, crf_v, cap):
    """cap — стеля бітрейту (Мбіт/с): вода й пил інакше роздувають кліп до 14 МБ за 8 с."""
    dur = b - a
    vf = f'{vf},{GRADE},fade=t=in:st=0:d={FADE},fade=t=out:st={dur - FADE:.2f}:d={FADE}'
    base = ['ffmpeg', '-v', 'error', '-y', '-threads', '4', '-ss', str(a), '-to', str(b), '-i', str(src), '-vf', vf, '-threads', '4']
    subprocess.run(base + X264 + ['-crf', str(crf_h), '-maxrate', f'{cap}M', '-bufsize', f'{cap * 2}M', f'{out}.mp4'], check=True)
    subprocess.run(base + VP9 + ['-crf', str(crf_v), '-b:v', f'{cap * 0.7:.2f}M', f'{out}.webm'], check=True)   # constrained quality: crf + стеля b:v
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{dur / 2:.2f}', '-i', f'{out}.mp4', '-frames:v', '1',
                    '-c:v', 'libwebp', '-quality', '78', f'{out}.webp'], check=True)


def emit():
    """web/js/cine.js — єдине джерело для сторінки: розділи + атрибуція з маніфесту (руками не правити)."""
    keep = ('title', 'author', 'license', 'license_url', 'page')
    data = {'chapters': [{**{k: c[k] for k in ('id', 'word', 'line')}, 'credit': {k: CFG['sources'][c['source']][k] for k in keep}}
                         for c in CFG['chapters']]}
    (ROOT / 'web' / 'js' / 'cine.js').write_text(
        '/* Згенеровано tools/stock.py з config/stock.json — не правити руками. */\n'
        f'window.PBT_CINE = {json.dumps(data, ensure_ascii=False, indent=1)};\n', encoding='utf-8')


def main():
    if sys.argv[1:] == ['--emit']:
        check(); emit(); return
    check()
    OUT.mkdir(parents=True, exist_ok=True)
    for c in CFG['chapters']:
        src = REF / CFG['sources'][c['source']]['file']
        w = OUT / f'{c["id"]}-w'
        encode(src, c['from'], c['to'], 'scale=1920:1080:flags=lanczos,setsar=1', w, 23, 33, 3.5)
        # портрет 9:16: ширина кропу = ih·9/16, центр — focus (0…1 по ширині кадру)
        crop = f"crop=ih*9/16:ih:(iw-ih*9/16)*{c['focus']}:0,scale=720:1280:flags=lanczos,setsar=1"
        encode(src, c['from'], c['to'], crop, OUT / f'{c["id"]}-m', 25, 35, 1.2)
        sizes = {p.name: round(p.stat().st_size / 1024) for p in sorted(OUT.glob(c['id'] + '-*'))}
        print(c['id'], sizes)
    emit()
    print('→', OUT, 'разом КБ:', round(sum(f.stat().st_size for f in OUT.iterdir()) / 1024))


if __name__ == '__main__':
    main()
