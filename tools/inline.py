#!/usr/bin/env python3
"""Одно-файлова збірка: шрифти, CSS, JS, зображення й відео — як data:URI.
  dist/pbt-site.html          — повний документ (з диска, без сервера; форма → резервна панель із текстом заявки)
  dist/pbt-site.artifact.html — фрагмент без <html>/<head>/<body> для публікації як Artifact
Бюджет 15,5 MiB: відео лише mp4; спочатку випадають петлі доказу, потім робіт,
останнім — відео героя. Постери лишаються; завелика збірка без відео завершується помилкою."""
import base64, json, mimetypes, re
from pathlib import Path

from bundle_contract import emit_fragment, fit_video_budget, inline_css, offline_source
from artifact_budget import audit_artifact, enforce_artifact_budget, _save_report

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / 'web'
DIST = ROOT / 'dist'
LIMIT = int(15.5 * 1024 * 1024)
BRAND_NAME = json.loads((ROOT / 'config' / 'business.json').read_text(encoding='utf-8'))['brand']['name']
mimetypes.add_type('image/webp', '.webp'); mimetypes.add_type('font/woff2', '.woff2'); mimetypes.add_type('video/mp4', '.mp4')


def data_uri(rel):
    p = WEB / rel
    mt = mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
    return f'data:{mt};base64,' + base64.b64encode(p.read_bytes()).decode()


source_html = offline_source((WEB / 'index.html').read_text(encoding='utf-8'))
html = source_html
fonts = re.sub(r'url\(\.\./fonts/([^)]+)\)', lambda m: 'url(' + data_uri('fonts/' + m.group(1)) + ')', (WEB / 'css' / 'fonts.css').read_text(encoding='utf-8'))
css = (WEB / 'css' / 'site.css').read_text(encoding='utf-8')
STYLES = (('css/fonts.css', fonts), ('css/site.css', css))
data = re.sub(r'"(media/[^"]+\.(?:webp|png|svg))"', lambda m: '"' + data_uri(m.group(1)) + '"', (WEB / 'js' / 'data.js').read_text(encoding='utf-8'))
geo_map = (WEB / 'media' / 'map' / 'oblasts.json').read_text(encoding='utf-8').strip()
blueprint = (WEB / 'js' / 'blueprint.js').read_text(encoding='utf-8')
dom = (WEB / 'js' / 'dom.js').read_text(encoding='utf-8')
physics = (WEB / 'js' / 'physics.js').read_text(encoding='utf-8')
clock = (WEB / 'js' / 'clock.js').read_text(encoding='utf-8')
site = (WEB / 'js' / 'site.js').read_text(encoding='utf-8')
cine = (WEB / 'js' / 'cine.js').read_text(encoding='utf-8')
CINE_IDS = re.findall(r'"id": "([a-z]+)"', cine)
html = re.sub(r'((?:src|href|poster)=")(media/[^"]+\.(?:webp|png))(")', lambda m: m.group(1) + data_uri(m.group(2)) + m.group(3), html)
html = re.sub(r' srcset="[^"]*"', '', html)
html = re.sub(r'<link rel="preload"[^>]*>\n?', '', html)


def assemble(videos):
    vmap = ',\n'.join(f'"{n}.mp4": "{data_uri("media/video/" + n + ".mp4")}"' for n in videos)
    cmap = ',\n'.join(f'"{i}": "{data_uri("media/cine/" + i + "-w.webp")}"' for i in CINE_IDS)
    d = data + '\nwindow.PBT.geoMap = ' + geo_map + ';' + '\nwindow.PBT.videoData = {' + vmap + '};\nwindow.PBT.cinePosters = {' + cmap + '};\nwindow.PBT_BUNDLE = true;\n'
    h = inline_css(html, STYLES)
    h = h.replace('<script src="js/data.js"></script>', '<script>' + d + '</script>').replace('<script src="js/cine.js"></script>', '<script>' + cine + '</script>').replace('<script src="js/dom.js"></script>', '<script>' + dom + '</script>').replace('<script src="js/physics.js"></script>', '<script>' + physics + '</script>').replace('<script src="js/clock.js"></script>', '<script>' + clock + '</script>').replace('<script src="js/site.js"></script>', '<script>' + blueprint + '</script><script>' + site + '</script>')
    return h


ALL = ['hero-tall', 'hero-wide-720', 'job-voda', 'job-zemlia', 'job-trans', 'job-lis', 'job-demont', 'proof-amph', 'proof-long', 'proof-sunset', 'proof-trailer', 'proof-night', 'proof-winter']
page, videos = fit_video_budget(assemble, ALL, LIMIT)

head = re.search(r'<head>(.*?)</head>', page, re.S).group(1)
body = re.search(r'<body[^>]*>(.*?)</body>', page, re.S).group(1)
keep = re.findall(r'<meta (?:name|property)="(?:description|og:[a-z:]+)"[^>]*>|<style>.*?</style>|<script type="application/ld\+json">.*?</script>', head, re.S)
early = re.search(r'<script>\s*/\* Профіль.*?</script>', head, re.S).group(0)
frag = emit_fragment(BRAND_NAME, keep, early, body)
if len(frag.encode('utf-8')) > LIMIT:
    raise ValueError('Portable fragment exceeds the byte budget')
DIST.mkdir(exist_ok=True)
(DIST / 'pbt-site.html').write_text(page, encoding='utf-8')
(DIST / 'pbt-site.artifact.html').write_text(frag, encoding='utf-8')
for f in ('pbt-site.html', 'pbt-site.artifact.html'):
    print(f, round((DIST / f).stat().st_size / 1048576, 2), 'MB', '| відео у бандлі:', len(videos), '/', len(ALL))

# Багатофайловий артефакт: сторінка-фрагмент (CSS/JS/шрифти інлайн) + медіа поруч відносними шляхами, лише mp4.
# Повна якість: усі петлі й кіно-сцена «Масштаб»; бюджет одного публікування 64 МБ.
import shutil
MULTI = DIST / 'artifact'
# Прев'ю в Artifact показує героя лише в 720 (window.PBT.heroSD): 1920-копія (9,4 МБ) не вміщається в 64 МБ
# одного публікування. Живий сайт і однофайлова збірка не змінюються; жодне відео не перекодовується.
ARTIFACT_OMIT = frozenset({'media/video/hero-wide.mp4'})
shutil.rmtree(MULTI, ignore_errors=True)
d = (WEB / 'js' / 'data.js').read_text(encoding='utf-8') + '\nwindow.PBT.geoMap = ' + geo_map + ';' + '\nwindow.PBT.mp4Only = true;\nwindow.PBT.heroSD = true;\nwindow.PBT_BUNDLE = true;\n'
h = source_html
h = inline_css(h, STYLES)
h = h.replace('<script src="js/data.js"></script>', '<script>' + d + '</script>').replace('<script src="js/cine.js"></script>', '<script>' + cine + '</script>').replace('<script src="js/dom.js"></script>', '<script>' + dom + '</script>').replace('<script src="js/physics.js"></script>', '<script>' + physics + '</script>').replace('<script src="js/clock.js"></script>', '<script>' + clock + '</script>').replace('<script src="js/site.js"></script>', '<script>' + blueprint + '</script><script>' + site + '</script>')
h = re.sub(r'<link rel="preload"[^>]*>\n?', '', h)
mhead = re.search(r'<head>(.*?)</head>', h, re.S).group(1)
mbody = re.search(r'<body[^>]*>(.*?)</body>', h, re.S).group(1)
mkeep = re.findall(r'<meta (?:name|property)="(?:description|og:[a-z:]+)"[^>]*>|<style>.*?</style>|<script type="application/ld\+json">.*?</script>', mhead, re.S)
mearly = re.search(r'<script>\s*/\* Профіль.*?</script>', mhead, re.S).group(0)
MULTI.mkdir(parents=True)
(MULTI / 'index.html').write_text(emit_fragment(BRAND_NAME, mkeep, mearly, mbody), encoding='utf-8')
n = 0
for f in sorted((WEB / 'media').rglob('*')):
    if f.relative_to(WEB).as_posix() in ARTIFACT_OMIT:
        continue
    if f.is_file() and (f.suffix in ('.mp4', '.webp', '.png', '.svg', '.jpg') or f.name == 'plainbud-logo.webm'):   # логотип — лише webm (альфа)
        t = MULTI / f.relative_to(WEB); t.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(f, t); n += 1
# Аудит фактичних байтів ДО підгонки. Жоден кліп не пропускається.
preflight = audit_artifact(MULTI)
_save_report(preflight, DIST / 'artifact-budget-preflight.json')
# Source-derived media is copied byte-for-byte: no encoding inside the build.
# Publication remains HOLD until a separately quality-reviewed media asset pack fits.
tot = sum(p.stat().st_size for p in MULTI.rglob('*') if p.is_file())
budget = enforce_artifact_budget(MULTI, DIST / 'artifact-budget.json')
if budget['total_bytes'] != tot or budget['asset_count'] != n + 1:
    raise ValueError('Multifile artifact changed during budget verification')
print('artifact/', n + 1, 'файлів,', round(tot / 1048576, 1), 'MB', '| budget verified')
