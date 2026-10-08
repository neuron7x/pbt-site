#!/usr/bin/env python3
"""Супер-роздільність для кліпів клієнта: TikTok віддає максимум 576×1024 (yt-dlp -F, 08.10.2026), а сайт кропить смугу 576×324
і показує її на 1280–1920 px ⇒ пікселі. Real-ESRGAN realesr-general-x4v3 (BSD-3, xinntao/Real-ESRGAN v0.2.5.0) на GPU:
references/<name>.mp4 → references/sr/<name>.mp4 рівно 2× (1152×2048), проміжний H.264 crf 12. tools/media.py бере sr/, якщо є.

Fail-closed: вага з іншим sha256 або без CUDA — вихід 1. Кадри йдуть потоком ffmpeg → GPU → ffmpeg; у пам'яті один пакет.
Сила знешумлення (denoise, 0…1) змішує ваги x4v3 і wdn-x4v3, як у Real-ESRGAN: стиснений TikTok шумить блоками,
тож за замовчуванням 0.5 — блоки геть, текстура лишається."""
import hashlib, json, subprocess, sys
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / 'references'
OUT = REF / 'sr'
W_DIR = Path.home() / '.cache' / 'pbt-sr'
WEIGHTS = {   # https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/<name>.pth
    'realesr-general-x4v3': '8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292',
    'realesr-general-wdn-x4v3': '1641f8c4464b9f097c9fdda5589273713f67cf59f3d909e0bd688f0cee269dca',
}


class SRVGGNetCompact(nn.Module):
    """Архітектура з Real-ESRGAN (BSD-3): 32 згортки 64 канали + PReLU, PixelShuffle ×4, залишок — nearest-апскейл входу."""
    def __init__(self, feat=64, convs=32, up=4):
        super().__init__()
        self.up = up
        body = [nn.Conv2d(3, feat, 3, 1, 1), nn.PReLU(feat)]
        for _ in range(convs):
            body += [nn.Conv2d(feat, feat, 3, 1, 1), nn.PReLU(feat)]
        body += [nn.Conv2d(feat, 3 * up * up, 3, 1, 1)]
        self.body = nn.ModuleList(body)
        self.shuffle = nn.PixelShuffle(up)

    def forward(self, x):
        y = x
        for m in self.body:
            y = m(y)
        return self.shuffle(y) + F.interpolate(x, scale_factor=self.up, mode='nearest')


def load(denoise):
    sd = {}
    for name, sha in WEIGHTS.items():
        p = W_DIR / f'{name}.pth'
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != sha:
            sys.exit(f'{p}: немає або sha256 ≠ {sha[:12]} — завантажити з релізу Real-ESRGAN v0.2.5.0')
        sd[name] = torch.load(p, map_location='cpu', weights_only=True)
        sd[name] = sd[name].get('params', sd[name])
    a, b = sd['realesr-general-x4v3'], sd['realesr-general-wdn-x4v3']
    net = SRVGGNetCompact()
    net.load_state_dict({k: (1 - denoise) * a[k] + denoise * b[k] for k in a})
    return net.eval().half().cuda()


def probe(src):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate',
                          '-of', 'json', str(src)], capture_output=True, text=True, check=True).stdout
    s = json.loads(out)['streams'][0]
    n, d = s['r_frame_rate'].split('/')
    return s['width'], s['height'], f'{n}/{d}'


@torch.inference_mode()
def upscale(name, denoise=0.5, batch=2):
    if not torch.cuda.is_available():
        sys.exit('немає CUDA')
    src = REF / f'{name}.mp4'
    w, h, fps = probe(src)
    net = load(denoise)
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f'{name}.mp4'
    tmp = dst.with_suffix('.part.mp4')
    rd = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(src), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    wr = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w * 2}x{h * 2}', '-r', fps, '-i', '-',
                           '-c:v', 'libx264', '-preset', 'medium', '-crf', '12', '-pix_fmt', 'yuv420p', '-threads', '4', str(tmp)],
                          stdin=subprocess.PIPE)
    fsz, n = w * h * 3, 0
    while True:
        buf = [rd.stdout.read(fsz) for _ in range(batch)]
        buf = [b for b in buf if len(b) == fsz]
        if not buf:
            break
        x = torch.from_numpy(np.stack([np.frombuffer(b, np.uint8).reshape(h, w, 3) for b in buf])).cuda()
        x = x.permute(0, 3, 1, 2).half() / 255
        y = net(x)                                                            # ×4
        y = F.interpolate(y.float(), size=(h * 2, w * 2), mode='area')       # ×4 → ×2 усередненням: менше артефактів, ніж пряме ×2
        y = (y.clamp(0, 1) * 255).round().byte().permute(0, 2, 3, 1).cpu().numpy()
        for f in y:
            wr.stdin.write(f.tobytes())
        n += len(buf)
    rd.wait(); wr.stdin.close(); wr.wait()
    if rd.returncode or wr.returncode or n == 0:
        tmp.unlink(missing_ok=True)
        sys.exit(f'{name}: ffmpeg {rd.returncode}/{wr.returncode}, кадрів {n}')
    tmp.replace(dst)
    print(name, f'{w}×{h} → {w * 2}×{h * 2}', n, 'кадрів')


if __name__ == '__main__':
    names = sys.argv[1:] or sorted(p.stem for p in REF.glob('*.mp4'))
    for nm in names:
        upscale(nm)
