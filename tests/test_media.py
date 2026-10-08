"""Сторож якості відео: роздільність і кадри — з файлів, а не з обіцянок у документації (ffprobe)."""
import json, shutil, subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / 'web' / 'media' / 'video'
pytestmark = pytest.mark.skipif(not shutil.which('ffprobe'), reason='немає ffprobe')


def dims(p):
    s = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                                   '-of', 'json', str(p)], capture_output=True, text=True, check=True).stdout)['streams'][0]
    return s['width'], s['height']


@pytest.mark.parametrize('name,wh', [('hero-wide', (1920, 1080)), ('hero-wide-720', (1280, 720)), ('hero-tall', (720, 1280))])
def test_hero_resolution(name, wh):
    for ext in ('mp4', 'webm'):
        assert dims(V / f'{name}.{ext}') == wh, f'{name}.{ext}'


def test_cards_are_960():
    clips = sorted(p for p in V.glob('*.mp4') if p.stem.startswith(('job-', 'proof-')))
    assert len(clips) == 11
    bad = {p.stem: dims(p) for p in clips if dims(p) != (960, 540)}
    assert not bad, bad
