"""Artifact-прев'ю вміщається в 64 МіБ лише без 1920-копії героя; живий сайт її зберігає."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 64 * 1024 * 1024


def _build(tmp_path):
    tree = tmp_path / 'tree'
    for name in ('tools', 'config', 'web', 'data'):
        shutil.copytree(ROOT / name, tree / name, ignore=shutil.ignore_patterns('*.db*', '*.log', '.ip_salt', '__pycache__'))
    proc = subprocess.run([sys.executable, 'tools/inline.py'], cwd=tree, capture_output=True, text=True, timeout=300)
    return tree, proc


def test_multifile_artifact_fits_budget_without_hd_hero_and_keeps_720(tmp_path):
    tree, proc = _build(tmp_path)
    assert proc.returncode == 0, proc.stderr
    art = tree / 'dist' / 'artifact'
    report = json.loads((tree / 'dist' / 'artifact-budget.json').read_text(encoding='utf-8'))
    total = sum(p.stat().st_size for p in art.rglob('*') if p.is_file())
    assert report['ok'] is True and report['total_bytes'] == total and total <= LIMIT
    assert not (art / 'media/video/hero-wide.mp4').exists()
    assert (art / 'media/video/hero-wide-720.mp4').is_file()
    assert (art / 'media/video/hero-tall.mp4').is_file()
    assert 'window.PBT.heroSD = true;' in (art / 'index.html').read_text(encoding='utf-8')
    # Живий сайт не втрачає 1920-копію.
    assert (ROOT / 'web/media/video/hero-wide.mp4').is_file()


def test_hero_hd_selector_honours_artifact_flag():
    src = (ROOT / 'web/js/site.js').read_text(encoding='utf-8')
    body = src[src.index('function heroHD()'):]
    body = body[:body.index('\n  }\n')]
    assert 'D.heroSD' in body and 'return false' in body
