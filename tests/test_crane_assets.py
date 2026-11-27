"""Графіка крана-глибиноміра згенерована tools/crane.py: блок у CSS мусить збігатися з генератором, а кадри — з адресами в CSS."""
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import crane  # noqa: E402

CSS = (ROOT / 'web' / 'css' / 'site.css').read_text(encoding='utf-8')
NS = '{http://www.w3.org/2000/svg}'


def test_css_block_is_exactly_what_the_generator_emits():
    assert CSS.count(crane.BEGIN) == 1 and CSS.count(crane.END) == 1
    assert CSS[CSS.index(crane.BEGIN):CSS.index(crane.END) + len(crane.END)] == crane.css_block()
    assert subprocess.run([sys.executable, '-s', 'tools/crane.py', '--check'], cwd=ROOT, capture_output=True).returncode == 0


def test_check_fails_when_css_drifts_from_the_generator(tmp_path):
    tree = tmp_path / 'tree'
    (tree / 'tools').mkdir(parents=True)
    (tree / 'web' / 'css').mkdir(parents=True)
    (tree / 'tools' / 'crane.py').write_text((ROOT / 'tools' / 'crane.py').read_text(encoding='utf-8'), encoding='utf-8')
    (tree / 'web' / 'css' / 'site.css').write_text(CSS.replace('load-catch .5s', 'load-catch .6s', 1), encoding='utf-8')
    run = subprocess.run([sys.executable, '-s', 'tools/crane.py', '--check'], cwd=tree, capture_output=True, text=True)
    assert run.returncode == 1 and 'не відповідає' in run.stderr


def test_every_embedded_svg_is_well_formed_and_self_contained():
    for name, svg in (('rope', crane.ROPE), ('hook', crane.HOOK), ('sheet', crane.sheet()), ('impact', crane.impact_dollars())):
        assert '\n' not in crane.uri(svg) and '\r' not in crane.uri(svg), name
        root = ET.fromstring(svg)
        assert root.tag == NS + 'svg', name
        ids = {e.get('id') for e in root.iter() if e.get('id')}
        refs = set(re.findall(r"url\(#(\w+)\)", svg)) | {e.get('href')[1:] for e in root.iter(NS + 'use')}
        assert refs <= ids, (name, refs - ids)                                   # кожне посилання веде на власний елемент
        assert 'http' not in svg.replace('http://www.w3.org/2000/svg', ''), name   # жодних зовнішніх ресурсів
        assert '<script' not in svg and '<image' not in svg and 'foreignObject' not in svg, name


def test_sheet_has_one_frame_per_declared_slot_and_nothing_spills_between_frames():
    root = ET.fromstring(crane.sheet())
    assert root.get('viewBox') == f"0 0 {crane.FRAMES['count'] * crane.FW} {crane.FH}"
    defs = {g.get('id'): g for g in root.find(NS + 'defs') if g.tag == NS + 'g'}
    occupied = set()
    for use in root.findall(NS + 'use'):
        ref = use.get('href')[1:]
        if use.get('transform'):
            match = re.match(r'translate\((\d+) (\d+)\)', use.get('transform'))
            x, y = int(match[1]) - crane.FW, int(match[2])
        else:
            x, y = int(use.get('x')), int(use.get('y'))
        frame = x // crane.FW
        width = max(int(r.get('x')) + int(r.get('width')) for r in defs[ref])
        height = max(int(r.get('y')) + int(r.get('height')) for r in defs[ref])
        assert x + width <= (frame + 1) * crane.FW, (ref, x)
        assert y + height <= crane.FH, (ref, y)
        occupied.add(frame)
    assert occupied == set(range(crane.FRAMES['count']))                         # порожніх кадрів немає


def test_css_addresses_only_existing_frames():
    block = crane.css_block()
    step = crane.FW * crane.CELL
    xs = {int(v) for v in re.findall(r'background-position-x:-?(\d+)px', block)} | {0}
    assert xs == {0, 2 * step, 12 * step, 13 * step, 14 * step, 26 * step, 27 * step}, sorted(xs)
    assert all(x % step == 0 and x // step <= crane.FRAMES['count'] - 1 for x in xs)
    assert f"{crane.FRAMES['count'] * step}px {crane.FH * crane.CELL}px" in block   # background-size = весь аркуш


def test_generator_is_deterministic_across_hash_seeds_and_locales():
    runs = [subprocess.run([sys.executable, '-s', '-c', 'import sys; sys.path.insert(0, "tools"); import crane; sys.stdout.buffer.write(crane.css_block().encode())'],
                           cwd=ROOT, capture_output=True, env={'PYTHONHASHSEED': seed, 'PATH': '/usr/bin:/bin', 'LC_ALL': locale})
            for seed, locale in (('0', 'C'), ('1', 'C.UTF-8'), ('4242', 'POSIX'))]
    assert [r.returncode for r in runs] == [0, 0, 0], [r.stderr[-200:] for r in runs]
    assert len({r.stdout for r in runs}) == 1 and runs[0].stdout.decode('utf-8') == crane.css_block()


def test_palette_is_the_brand_palette_and_no_third_party_character_is_named():
    assert crane.PAL['Y'] == '#FDC501' and crane.PAL['B'] == '#1238A8'
    source = (ROOT / 'tools' / 'crane.py').read_text(encoding='utf-8').lower()
    assert 'mario' not in source and 'nintendo' not in source and 'маріо' not in source


def test_dollar_rain_changes_position_and_fades_across_the_lift_cycle():
    root = ET.fromstring(crane.sheet())
    particles = [use for use in root.findall(NS + 'use') if use.get('href') in ('#d', '#d-small')]
    rain = range(crane.FRAMES['rain'], crane.FRAMES['cash'])
    by_frame = {frame: [use for use in particles if int(use.get('x')) // crane.FW == frame] for frame in rain}
    assert all(2 <= len(group) <= 3 for group in by_frame.values())
    assert sum(map(len, by_frame.values())) == len(particles)
    positions = [tuple((int(use.get('x')) % crane.FW, int(use.get('y'))) for use in group) for group in by_frame.values()]
    assert len(set(positions)) == len(rain)
    assert any(0 < float(use.get('opacity')) < 1 for use in particles)
