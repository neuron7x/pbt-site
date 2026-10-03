#!/usr/bin/env python3
"""Одно-файлова збірка сайту: шрифти, CSS, JS, зображення — як data:URI.
  dist/pbt-site.html          — повний документ (відкривається з диска, без сервера; форма → резервна панель з текстом заявки)
  dist/pbt-site.artifact.html — фрагмент без <html>/<head>/<body> для публікації як Artifact (обгортку додає платформа)
Герой у бандлі — кожен другий кадр (легше вдвічі); window.PBT_BUNDLE=true вимикає /api/*."""
import base64, mimetypes, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / 'web'
DIST = ROOT / 'dist'
mimetypes.add_type('image/webp', '.webp'); mimetypes.add_type('font/woff2', '.woff2')


def data_uri(rel):
    p = WEB / rel
    mt = mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
    return f'data:{mt};base64,' + base64.b64encode(p.read_bytes()).decode()


def inline_media(text, attr_re):
    return re.sub(attr_re, lambda m: m.group(1) + data_uri(m.group(2)) + m.group(3), text)


html = (WEB / 'index.html').read_text(encoding='utf-8')
fonts = (WEB / 'css' / 'fonts.css').read_text(encoding='utf-8')
fonts = re.sub(r'url\(\.\./fonts/([^)]+)\)', lambda m: 'url(' + data_uri('fonts/' + m.group(1)) + ')', fonts)
css = (WEB / 'css' / 'site.css').read_text(encoding='utf-8')
data = (WEB / 'js' / 'data.js').read_text(encoding='utf-8')
site = (WEB / 'js' / 'site.js').read_text(encoding='utf-8')

# зображення в даних (парк, матеріали, постери, логотипи)
data = re.sub(r'"(media/[^"]+\.(?:webp|png|svg))"', lambda m: '"' + data_uri(m.group(1)) + '"', data)
frames = sorted((WEB / 'media' / 'hero').glob('f_*.webp'))[::2]
data += '\nwindow.PBT.heroFrames = [' + ','.join('"' + data_uri(f.relative_to(WEB).as_posix()) + '"' for f in frames) + '];\nwindow.PBT_BUNDLE = true;\n'

# зображення в розмітці
html = inline_media(html, r'((?:src|href)=")(media/[^"]+\.(?:webp|png))(")')
html = re.sub(r' srcset="[^"]*"', '', html)
# стилі та скрипти — всередину
html = html.replace('<link rel="stylesheet" href="css/fonts.css">', '<style>' + fonts + '</style>')
html = html.replace('<link rel="stylesheet" href="css/site.css">', '<style>' + css + '</style>')
html = re.sub(r'<link rel="preload"[^>]*>\n?', '', html)
html = html.replace('<script src="js/data.js"></script>', '<script>' + data + '</script>')
html = html.replace('<script src="js/site.js"></script>', '<script>' + site + '</script>')
DIST.mkdir(exist_ok=True)
(DIST / 'pbt-site.html').write_text(html, encoding='utf-8')

# фрагмент для Artifact: без doctype/html/head/body; <title> і <style> першими
head = re.search(r'<head>(.*?)</head>', html, re.S).group(1)
body = re.search(r'<body[^>]*>(.*?)</body>', html, re.S).group(1)
keep = re.findall(r'<title>.*?</title>|<meta (?:name|property)="(?:description|og:[a-z:]+)"[^>]*>|<style>.*?</style>|<script>(?!\s*/\* Профіль).*?</script>|<script type="application/ld\+json">.*?</script>', head, re.S)
early = re.search(r'<script>\s*/\* Профіль.*?</script>', head, re.S).group(0)
frag = '\n'.join(keep) + '\n' + early + '\n' + body
frag = frag.replace('<body class="home">', '')
(DIST / 'pbt-site.artifact.html').write_text(frag, encoding='utf-8')
for f in ('pbt-site.html', 'pbt-site.artifact.html'):
    print(f, round((DIST / f).stat().st_size / 1048576, 2), 'MB')
