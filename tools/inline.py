#!/usr/bin/env python3
"""Одно-файлова збірка: шрифти, CSS, JS, зображення й відео — як data:URI.
  dist/pbt-site.html          — повний документ (з диска, без сервера; форма → резервна панель із текстом заявки)
  dist/pbt-site.artifact.html — фрагмент без <html>/<head>/<body> для публікації як Artifact
Бюджет артефакту 16 МБ: відео лише mp4; якщо не вміщається — спочатку випадають петлі доказу, потім робіт (постери лишаються)."""
import base64, mimetypes, re
from pathlib import Path

from bundle_contract import inline_css

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / 'web'
DIST = ROOT / 'dist'
LIMIT = 15.5 * 1024 * 1024
mimetypes.add_type('image/webp', '.webp'); mimetypes.add_type('font/woff2', '.woff2'); mimetypes.add_type('video/mp4', '.mp4')


def data_uri(rel):
    p = WEB / rel
    mt = mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
    return f'data:{mt};base64,' + base64.b64encode(p.read_bytes()).decode()


html = (WEB / 'index.html').read_text(encoding='utf-8')
fonts = re.sub(r'url\(\.\./fonts/([^)]+)\)', lambda m: 'url(' + data_uri('fonts/' + m.group(1)) + ')', (WEB / 'css' / 'fonts.css').read_text(encoding='utf-8'))
css = (WEB / 'css' / 'site.css').read_text(encoding='utf-8')
STYLES = (('css/fonts.css', fonts), ('css/site.css', css))
data = re.sub(r'"(media/[^"]+\.(?:webp|png|svg))"', lambda m: '"' + data_uri(m.group(1)) + '"', (WEB / 'js' / 'data.js').read_text(encoding='utf-8'))
site = (WEB / 'js' / 'site.js').read_text(encoding='utf-8')
cine = (WEB / 'js' / 'cine.js').read_text(encoding='utf-8')
CINE_IDS = re.findall(r'"id": "([a-z]+)"', cine)
html = re.sub(r'((?:src|href|poster)=")(media/[^"]+\.(?:webp|png))(")', lambda m: m.group(1) + data_uri(m.group(2)) + m.group(3), html)
html = re.sub(r' srcset="[^"]*"', '', html)
html = re.sub(r'<link rel="preload"[^>]*>\n?', '', html)


def assemble(videos):
    vmap = ',\n'.join(f'"{n}.mp4": "{data_uri("media/video/" + n + ".mp4")}"' for n in videos)
    cmap = ',\n'.join(f'"{i}": "{data_uri("media/cine/" + i + "-w.webp")}"' for i in CINE_IDS)
    d = data + '\nwindow.PBT.videoData = {' + vmap + '};\nwindow.PBT.cinePosters = {' + cmap + '};\nwindow.PBT_BUNDLE = true;\n'
    h = inline_css(html, STYLES)
    h = h.replace('<script src="js/data.js"></script>', '<script>' + d + '</script>').replace('<script src="js/cine.js"></script>', '<script>' + cine + '</script>').replace('<script src="js/site.js"></script>', '<script>' + site + '</script>')
    return h


ALL = ['hero-tall', 'hero-wide-720', 'job-voda', 'job-zemlia', 'job-trans', 'job-lis', 'job-demont', 'proof-amph', 'proof-long', 'proof-sunset', 'proof-trailer', 'proof-night', 'proof-winter']
videos = list(ALL)
page = assemble(videos)
while len(page.encode()) > LIMIT and len(videos) > 2:
    videos.pop()                                   # з кінця: доказ → роботи; герой лишається
    page = assemble(videos)
DIST.mkdir(exist_ok=True)
(DIST / 'pbt-site.html').write_text(page, encoding='utf-8')

head = re.search(r'<head>(.*?)</head>', page, re.S).group(1)
body = re.search(r'<body[^>]*>(.*?)</body>', page, re.S).group(1)
keep = re.findall(r'<meta (?:name|property)="(?:description|og:[a-z:]+)"[^>]*>|<style>.*?</style>|<script type="application/ld\+json">.*?</script>', head, re.S)
early = re.search(r'<script>\s*/\* Профіль.*?</script>', head, re.S).group(0)
frag = '<title>ПБТ · ПолтаваБудТехніка</title>\n' + '\n'.join(keep) + '\n' + early + '\n' + body
(DIST / 'pbt-site.artifact.html').write_text(frag, encoding='utf-8')
for f in ('pbt-site.html', 'pbt-site.artifact.html'):
    print(f, round((DIST / f).stat().st_size / 1048576, 2), 'MB', '| відео у бандлі:', len(videos), '/', len(ALL))

# Багатофайловий артефакт: сторінка-фрагмент (CSS/JS/шрифти інлайн) + медіа поруч відносними шляхами, лише mp4.
# Повна якість: усі петлі й кіно-сцена «Масштаб»; бюджет одного публікування 64 МБ.
import shutil
MULTI = DIST / 'artifact'
shutil.rmtree(MULTI, ignore_errors=True)
d = (WEB / 'js' / 'data.js').read_text(encoding='utf-8') + '\nwindow.PBT.mp4Only = true;\nwindow.PBT_BUNDLE = true;\n'
h = (WEB / 'index.html').read_text(encoding='utf-8')
h = inline_css(h, STYLES)
h = h.replace('<script src="js/data.js"></script>', '<script>' + d + '</script>').replace('<script src="js/cine.js"></script>', '<script>' + cine + '</script>').replace('<script src="js/site.js"></script>', '<script>' + site + '</script>')
h = re.sub(r'<link rel="preload"[^>]*>\n?', '', h)
mhead = re.search(r'<head>(.*?)</head>', h, re.S).group(1)
mbody = re.search(r'<body[^>]*>(.*?)</body>', h, re.S).group(1)
mkeep = re.findall(r'<meta (?:name|property)="(?:description|og:[a-z:]+)"[^>]*>|<style>.*?</style>|<script type="application/ld\+json">.*?</script>', mhead, re.S)
mearly = re.search(r'<script>\s*/\* Профіль.*?</script>', mhead, re.S).group(0)
MULTI.mkdir(parents=True)
(MULTI / 'index.html').write_text('<title>ПБТ · ПолтаваБудТехніка</title>\n' + '\n'.join(mkeep) + '\n' + mearly + '\n' + mbody, encoding='utf-8')
n = 0
for f in sorted((WEB / 'media').rglob('*')):
    if f.is_file() and (f.suffix in ('.mp4', '.webp', '.png', '.svg', '.jpg') or f.name == 'pbt-logo.webm'):   # логотип — лише webm (альфа)
        t = MULTI / f.relative_to(WEB); t.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(f, t); n += 1
tot = sum(p.stat().st_size for p in MULTI.rglob('*') if p.is_file())
print('artifact/', n + 1, 'файлів,', round(tot / 1048576, 1), 'MB')
