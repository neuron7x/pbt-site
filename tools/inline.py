#!/usr/bin/env python3
"""Одно-файлова збірка: шрифти, CSS, JS, зображення й відео — як data:URI.
  dist/pbt-site.html          — повний документ (з диска, без сервера; форма → резервна панель із текстом заявки)
  dist/pbt-site.artifact.html — фрагмент без <html>/<head>/<body> для публікації як Artifact
Бюджет артефакту 16 МБ: відео лише mp4; якщо не вміщається — спочатку випадають петлі доказу, потім робіт (постери лишаються)."""
import base64, mimetypes, re
from pathlib import Path

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
data = re.sub(r'"(media/[^"]+\.(?:webp|png|svg))"', lambda m: '"' + data_uri(m.group(1)) + '"', (WEB / 'js' / 'data.js').read_text(encoding='utf-8'))
site = (WEB / 'js' / 'site.js').read_text(encoding='utf-8')
html = re.sub(r'((?:src|href|poster)=")(media/[^"]+\.(?:webp|png))(")', lambda m: m.group(1) + data_uri(m.group(2)) + m.group(3), html)
html = re.sub(r' srcset="[^"]*"', '', html)
html = re.sub(r'<link rel="preload"[^>]*>\n?', '', html)


def assemble(videos):
    vmap = ',\n'.join(f'"{n}.mp4": "{data_uri("media/video/" + n + ".mp4")}"' for n in videos)
    d = data + '\nwindow.PBT.videoData = {' + vmap + '};\nwindow.PBT_BUNDLE = true;\n'
    h = html.replace('<link rel="stylesheet" href="css/fonts.css">', '<style>' + fonts + '</style>').replace('<link rel="stylesheet" href="css/site.css">', '<style>' + css + '</style>')
    h = h.replace('<script src="js/data.js"></script>', '<script>' + d + '</script>').replace('<script src="js/site.js"></script>', '<script>' + site + '</script>')
    return h


ALL = ['hero-tall', 'hero-wide', 'job-voda', 'job-zemlia', 'job-trans', 'job-lis', 'job-demont', 'proof-amph', 'proof-long', 'proof-sunset', 'proof-trailer', 'proof-night', 'proof-winter']
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
