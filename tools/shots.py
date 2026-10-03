#!/usr/bin/env python3
"""Знімки екранів для огляду: десктоп (герой у 3 точках скролу + повна сторінка) і телефон (повна сторінка).
Використання: tools/shots.py http://127.0.0.1:4180 [artifacts/shots]"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

base = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:4180'
out = Path(sys.argv[2] if len(sys.argv) > 2 else 'artifacts/shots'); out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch()
    d = b.new_context(viewport={'width': 1440, 'height': 900}, device_scale_factor=1).new_page()
    d.goto(base, wait_until='networkidle'); d.wait_for_timeout(1200)
    for i, y in enumerate((0, .9, 1.9)):
        d.evaluate(f'scrollTo({{top: innerHeight * {y}, behavior: "instant"}})'); d.wait_for_timeout(900)
        d.screenshot(path=str(out / f'desktop-hero-{i}.png'))
    d.evaluate('scrollTo({top: 0, behavior: "instant"})'); d.wait_for_timeout(300)
    d.screenshot(path=str(out / 'desktop-full.png'), full_page=True)
    m = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True).new_page()
    m.goto(base, wait_until='networkidle'); m.wait_for_timeout(1200)
    m.screenshot(path=str(out / 'mobile-hero.png'))
    m.evaluate('scrollTo({top: innerHeight * 1.6, behavior: "instant"})'); m.wait_for_timeout(900)
    m.screenshot(path=str(out / 'mobile-hero-dive.png'))
    m.screenshot(path=str(out / 'mobile-full.png'), full_page=True)
    b.close()
print('→', out, sorted(f.name for f in out.iterdir()))
