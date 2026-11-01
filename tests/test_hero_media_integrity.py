"""Регресії реальних кадрів: летербокс героя, межі панелей і перший постер."""
import io
import runpy
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / 'web/media/video'
PROBES = (0.4, 3.5, 7.2, 9.5, 11.2, 12.8, 15.2)


def frame(path, timestamp):
    assert shutil.which('ffmpeg'), 'ffmpeg потрібний для перевірки фактичних кадрів'
    result = subprocess.run(
        ['ffmpeg', '-v', 'error', '-threads', '1', '-ss', str(timestamp), '-i', str(path),
         '-vf', 'scale=160:-2', '-frames:v', '1', '-threads', '1',
         '-f', 'image2pipe', '-vcodec', 'png', 'pipe:1'],
        capture_output=True, check=True, timeout=20,
    )
    return Image.open(io.BytesIO(result.stdout)).convert('RGB')


@pytest.mark.parametrize('name', ('hero-wide', 'hero-wide-720', 'hero-tall'))
@pytest.mark.parametrize('ext', ('mp4', 'webm'))
def test_hero_montage_has_no_embedded_letterbox(name, ext):
    """Кожен фрагмент монтажу, обидва кодеки; саме 12.8 s відтворює старий дефект."""
    for timestamp in PROBES:
        pixels = np.asarray(frame(VIDEO / f'{name}.{ext}', timestamp).convert('L'))
        for edge in (pixels[:4], pixels[-4:]):
            assert edge.mean() > 8, f'{name}.{ext}, {timestamp}s: чорна смуга, mean={edge.mean():.2f}'


@pytest.mark.parametrize('name', ('hero-wide', 'hero-wide-720', 'hero-tall'))
def test_hero_poster_shows_the_amphibious_machine_frame(name):
    """Перевіряє поставлений файл: зміна лише константи збірки тест не задовольнить."""
    reference = frame(VIDEO / f'{name}.mp4', 7.2)
    poster = Image.open(VIDEO / f'{name}.webp').convert('RGB').resize(reference.size)
    difference = np.abs(np.asarray(poster, dtype=float) - np.asarray(reference, dtype=float)).mean()
    assert difference < 8, f'{name}: постер не відповідає кадру амфібії, MAE={difference:.2f}'


@pytest.mark.parametrize('ext', ('webp', 'mp4', 'webm'))
def test_amphibious_clip_has_no_foreign_panel_above_the_sky(ext):
    """У цьому кліпі зверху небо; стара смуга іншої панелі давала перепад 156/255."""
    path = VIDEO / f'proof-amph.{ext}'
    for timestamp in (0.4, 2.5, 5.5):
        image = Image.open(path).convert('RGB').resize((160, 90)) if ext == 'webp' else frame(path, timestamp)
        pixels = np.asarray(image.convert('L'))
        contrast = abs(float(pixels[:3].mean()) - float(pixels[7:12].mean()))
        assert contrast < 45, f'proof-amph.{ext}, {timestamp}s: край сусідньої панелі, delta={contrast:.2f}'


def test_canonical_source_crops_stay_inside_visible_panels():
    media = runpy.run_path(str(ROOT / 'tools/media.py'))
    for parts, _, _ in media['BUILDS'].values():
        for _, _, _, crop in parts:
            width, height, x, y = map(int, crop.split(':'))
            assert min(width, height) > 0 and min(x, y) >= 0
            assert x + width <= 576 and y + height <= 1024

    for source, _, _, crop in media['BUILDS']['hero-tall'][0]:
        width, height, _, _ = map(int, crop.split(':'))
        assert width * 16 == height * 9, f'{source}: портретний кроп спотворює пропорції'

    sunset = next(part for part in media['BUILDS']['hero-tall'][0] if part[0] == 'sunset')
    width, height, _, y = map(int, sunset[3].split(':'))
    assert y >= 130 and y + height <= 893, 'sunset: кроп перетинає летербокс джерела'

    amph = media['BUILDS']['proof-amph'][0][0]
    _, height, _, y = map(int, amph[3].split(':'))
    assert y >= 354 and y + height <= 669, 'amph3: кроп захоплює сусідню панель'
