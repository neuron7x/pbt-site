#!/usr/bin/env python3
"""Карта областей як дані: web/media/map/oblasts.json (контури, назви, зона виїзду, центри bbox).

Раніше 27 контурів жили інлайн у index.html: 81 КБ сирих / 30,5 КБ gzip, 70 % документа на критичному шляху,
хоча секція «Де працюємо» — передостання. Тепер сторінка несе лише порожню рамку SVG з viewBox (без зсуву
розкладки), а site.js вантажить цей файл, коли секція наближається, і будує контури через createElementNS
(жодного розбору розмітки — сумісно з Trusted Types). Центри рахуються тут, щоб у браузері не було getBBox
посеред прокрутки (A/B 09.10: ривок 344 мс на CPU ×4).

  python3 tools/geo_map.py --extract   одноразово: з index.html → JSON (і порожня рамка в index.html)
  python3 tools/geo_map.py             перевірка: JSON валідний, центри збігаються з контурами (fail-closed)
"""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / 'web' / 'index.html'
OUT = ROOT / 'web' / 'media' / 'map' / 'oblasts.json'
SVG = re.compile(r'<svg xmlns="http://www.w3.org/2000/svg" viewBox="([\d .]+)" role="img" aria-labelledby="mapTitle">'
                 r'(<title id="mapTitle">[^<]*</title>)(.*?)</svg>', re.S)
PATH = re.compile(r'<path class="(obl(?: served)?)" data-name="([^"]*)" data-ua="([^"]*)" d="([^"]+)"\s*/?>(?:</path>)?')
NUM = re.compile(r'-?\d+(?:\.\d+)?')


def center(d):
    xs = [float(v) for v in NUM.findall(d)[0::2]]
    ys = [float(v) for v in NUM.findall(d)[1::2]]
    return [round((min(xs) + max(xs)) / 2, 1), round((min(ys) + max(ys)) / 2, 1)]


def extract():
    html = HTML.read_text(encoding='utf-8')
    m = SVG.search(html)
    if not m:
        raise SystemExit('inline map not found in index.html (already extracted?)')
    regions = [{'name': n, 'ua': ua, 'served': cls.endswith('served'), 'd': d, 'c': center(d)}
               for cls, n, ua, d in PATH.findall(m.group(3))]
    rest = PATH.sub('', m.group(3)).strip()
    if rest:
        raise SystemExit(f'unparsed markup inside the map: {rest[:120]!r}')
    data = {'schema': 'pbt-geo-map-v1', 'viewBox': m.group(1), 'regions': regions}
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    shell = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{m.group(1)}" role="img" aria-labelledby="mapTitle">'
             f'{m.group(2)}</svg>')
    HTML.write_text(html[:m.start()] + shell + html[m.end():], encoding='utf-8')
    print(f'extracted {len(regions)} regions → {OUT.relative_to(ROOT)}')


def check():
    data = json.loads(OUT.read_text(encoding='utf-8'))
    bad = []
    if data.get('schema') != 'pbt-geo-map-v1' or not re.fullmatch(r'0 0 \d+ \d+', data.get('viewBox', '')):
        bad.append('schema/viewBox')
    regions = data.get('regions') or []
    if len(regions) < 25:
        bad.append(f'regions {len(regions)} < 25')
    for r in regions:
        if not re.fullmatch(r'[MLZ0-9., -]+', r['d']):
            bad.append(f"{r['name']}: path has non-polyline commands")
        if r['c'] != center(r['d']):
            bad.append(f"{r['name']}: centre {r['c']} ≠ bbox centre {center(r['d'])}")
    if '<path class="obl' in HTML.read_text(encoding='utf-8'):
        bad.append('index.html still carries inline region paths')
    if bad:
        print('\n'.join(bad))
        return 1
    print(f'geo map OK: {len(regions)} regions')
    return 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--extract', action='store_true')
    sys.exit(extract() if ap.parse_args().extract else check())
