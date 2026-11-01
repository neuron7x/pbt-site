"""NET-06: public configuration crosses a trust boundary into the DOM; no value may execute."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOSTILE = '"><img src=x onerror="window.__xss=1"><a href="'
CONFIG = {
    'legalName': HOSTILE, 'address': HOSTILE, 'edrpou': HOSTILE, 'hours': {'mo-fr': HOSTILE, 'sa': HOSTILE, 'su': HOSTILE},
    'contacts': {
        'phone': '+380971234567" onmouseover="window.__xss=1', 'phone2': HOSTILE, 'viber': HOSTILE,
        'telegram': '@x"><script>window.__xss=1</script>', 'email': 'a@b.c"><img src=x onerror="window.__xss=1">',
        'tiktok': 'javascript:window.__xss=1', 'instagram': 'data:text/html,<script>parent.__xss=1</script>',
        'facebook': 'JaVaScRiPt:window.__xss=1', 'youtube': 'https://example.test/" onmouseover="window.__xss=1',
    },
}
UNSAFE_ATTRS = """() => {
  const bad = [];
  document.querySelectorAll('footer *, #channels *, [data-social] *, #kontakty *').forEach(el => {
    for (const a of el.attributes) {
      if (/^on/i.test(a.name)) bad.push(el.tagName + ':' + a.name);
      if (['href', 'src', 'xlink:href'].includes(a.name) && /^\\s*(javascript|data|vbscript):/i.test(a.value)) bad.push(el.tagName + ':' + a.value);
    }
    if (el.tagName === 'IMG' && el.getAttribute('src') === 'x') bad.push('injected-img');
    if (el.tagName === 'SCRIPT') bad.push('injected-script');
  });
  return bad;
}"""


def _load(browser, server, config):
    ctx = browser.new_context()
    page = ctx.new_page()
    violations = []
    page.on('console', lambda m: violations.append(m.text) if 'Content Security Policy' in m.text else None)
    page.on('dialog', lambda d: (violations.append('dialog'), d.dismiss()))
    page.route('**/api/config', lambda r: r.fulfill(status=200, content_type='application/json', body=json.dumps(config)))
    page.goto(server['base'], wait_until='load')
    page.wait_for_timeout(400)
    return ctx, page, violations


def test_hostile_public_config_is_inert_in_every_sink(browser, server):
    ctx, page, violations = _load(browser, server, CONFIG)
    try:
        assert page.evaluate(UNSAFE_ATTRS) == []
        assert page.evaluate('() => window.__xss') is None
        for link in page.locator('[data-social] a, #channels a').all():
            link.hover(force=True, timeout=1000)
        assert page.evaluate('() => window.__xss') is None
        # No payload reached a state where CSP had to save us: the code itself neutralized it.
        assert violations == []
    finally:
        ctx.close()


def test_positive_control_real_config_keeps_working_links(browser, server):
    good = {'contacts': {'phone': '+380971234567', 'telegram': '@pbt_test', 'email': 'info@example.test',
                         'viber': '+380971234567', 'instagram': 'https://instagram.example/pbt'}}
    ctx, page, _ = _load(browser, server, good)
    try:
        hrefs = page.evaluate("() => [...document.querySelectorAll('#channels a')].map(a => a.getAttribute('href'))")
        assert 'tel:+380971234567' in hrefs and 'https://t.me/pbt_test' in hrefs and 'mailto:info@example.test' in hrefs
        assert any(h.startswith('viber://chat?number=') for h in hrefs)
        assert page.locator('[data-social] a[href="https://instagram.example/pbt"]').count() > 0
    finally:
        ctx.close()


def test_dom_sink_inventory_is_complete_and_fails_on_a_new_sink(tmp_path):
    tool = ROOT / 'tools' / 'dom_sinks.py'
    ok = subprocess.run([sys.executable, str(tool), '--root', str(ROOT)], capture_output=True, text=True, timeout=30)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    copy = tmp_path / 'web' / 'js'
    copy.mkdir(parents=True)
    for f in (ROOT / 'web/js').glob('*.js'):
        (copy / f.name).write_bytes(f.read_bytes())
    (tmp_path / 'config').mkdir()
    (tmp_path / 'config/dom-sinks.json').write_bytes((ROOT / 'config/dom-sinks.json').read_bytes())
    with (copy / 'site.js').open('a', encoding='utf-8') as h:
        h.write('\ndocument.body.innerHTML = location.hash;\n')
    bad = subprocess.run([sys.executable, str(tool), '--root', str(tmp_path)], capture_output=True, text=True, timeout=30)
    assert bad.returncode == 1 and 'unreviewed_sink' in bad.stdout
