"""Sample text contrast against actual hero video frames, not a WCAG certification.

Each word/label is sampled in four horizontal regions with the text hidden,
while the video, overlays and button backgrounds remain rendered. The 95th
percentile is a bounded screenshot estimate, not a worst-pixel guarantee.
"""
import io
import json
import re

import pytest
from PIL import Image


def luminance(rgb):
    def linear(v):
        v = v / 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (linear(v) for v in rgb[:3])
    return .2126 * r + .7152 * g + .0722 * b


def worst_sample(image, target, viewport):
    """Worst of four strips; use the bright/dark 95th percentile toward ink."""
    scale_x = image.width / viewport['width']
    scale_y = image.height / viewport['height']
    x0 = max(0, round(target['x'] * scale_x))
    x1 = min(image.width, round((target['x'] + target['width']) * scale_x))
    y0 = max(0, round(target['y'] * scale_y))
    y1 = min(image.height, round((target['y'] + target['height']) * scale_y))
    assert x1 > x0 and y1 > y0, target
    fg = luminance(target['rgb'])
    worst = float('inf')
    for strip in range(4):
        left = x0 + (x1 - x0) * strip // 4
        right = x0 + (x1 - x0) * (strip + 1) // 4
        assert right > left, target
        pixels = image.crop((left, y0, right, y1)).get_flattened_data()
        levels = sorted(luminance(px) for px in pixels)
        # For each strip, take the percentile closest to the foreground;
        # if the strip spans the foreground, the conservative ratio is 1.
        lo, hi = levels[int((len(levels) - 1) * .05)], levels[int((len(levels) - 1) * .95)]
        bg = min(max(fg, lo), hi)
        ratio = (max(fg, bg) + .05) / (min(fg, bg) + .05)
        worst = min(worst, ratio)
    return worst


def targets(page):
    result = page.evaluate("""() => {
      const groups = [
        ['headline', '#heroTitle .w'], ['eyebrow', '#heroCenter .eyebrow'],
        ['fact', '#heroCenter .hero__stats b'], ['fact-label', '#heroCenter .hero__stats span'],
        ['action', '#heroCenter .row .btn']
      ];
      const items = [];
      for (const [group, selector] of groups) {
        for (const el of document.querySelectorAll(selector)) {
          const style = getComputedStyle(el), range = document.createRange();
          range.selectNodeContents(el);
          const rect = range.getBoundingClientRect();
          let ancestorsOpaque = true;
          for (let node = el; node; node = node.parentElement) {
            const parent = getComputedStyle(node);
            if (parent.display === 'none' || parent.visibility !== 'visible' ||
                parseFloat(parent.opacity) < 1) ancestorsOpaque = false;
          }
          items.push({group, text: el.textContent.trim(), color: style.webkitTextFillColor || style.color,
            ancestorsOpaque, visibility: style.visibility,
            fontSize: parseFloat(style.fontSize), fontWeight: parseInt(style.fontWeight, 10),
            x: rect.x, y: rect.y, width: rect.width, height: rect.height});
        }
      }
      return {viewport: {width: innerWidth, height: innerHeight}, items};
    }""")
    counts = {group: sum(x['group'] == group for x in result['items'])
              for group in ('headline', 'eyebrow', 'fact', 'fact-label', 'action')}
    assert counts == {'headline': 4, 'eyebrow': 1, 'fact': 4, 'fact-label': 4, 'action': 2}, counts
    for item in result['items']:
        assert item['text'] and item['ancestorsOpaque'] and item['visibility'] == 'visible', item
        m = re.fullmatch(r'rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)', item['color'])
        assert m and (m.group(4) is None or float(m.group(4)) == 1), item
        item['rgb'] = [int(m.group(i)) for i in range(1, 4)]
        assert item['width'] > 4 and item['height'] > 4, item
        assert item['x'] >= 0 and item['y'] >= 0, item
        assert item['x'] + item['width'] <= result['viewport']['width'] + 1, item
        assert item['y'] + item['height'] <= result['viewport']['height'] + 1, item
        large = item['fontSize'] >= 24 or (item['fontSize'] >= 18.6667 and item['fontWeight'] >= 700)
        item['minimum'] = 3.0 if large else 4.5
    return result


def hide_text(page):
    # Transparent ink preserves placement, background colors, borders and overlays.
    page.add_style_tag(content='''
      #heroTitle .w, #heroCenter .eyebrow, #heroCenter .hero__stats b,
      #heroCenter .hero__stats span, #heroCenter .row .btn {
        color: transparent !important; -webkit-text-fill-color: transparent !important;
        text-shadow: none !important;
      }
    ''')


def screenshot(page):
    return Image.open(io.BytesIO(page.screenshot())).convert('RGB')


@pytest.mark.parametrize('theme', ['sky', 'precision'])
@pytest.mark.parametrize('w,h,mobile', [(1440, 900, False), (390, 844, True)], ids=['desktop', 'phone'])
def test_hero_text_contrast_on_sampled_video_frames(page_factory, theme, w, h, mobile):
    page = page_factory(w, h, mobile=mobile)
    page.locator(f'[data-theme-choice="{theme}"]').click()
    page.wait_for_timeout(1800)
    evidence = targets(page)
    hide_text(page)
    results, fingerprints = [], []
    for frame in range(10):
        seek = page.evaluate("""async frame => {
          const v = document.querySelector('#heroVideo');
          const timeout = ms => new Promise(r => setTimeout(() => r(false), ms));
          if (v.readyState < 1) await Promise.race([
            new Promise(r => v.addEventListener('loadedmetadata', () => r(true), {once:true})), timeout(4000)]);
          if (!Number.isFinite(v.duration) || v.duration <= 0) return null;
          v.pause();
          const expected = Math.min(v.duration - .05, v.duration * frame / 10 + .2);
          const done = new Promise(r => v.addEventListener('seeked', () => r(true), {once:true}));
          v.currentTime = expected;
          if (!await Promise.race([done, timeout(3000)])) return null;
          return {expected, actual: v.currentTime};
        }""", frame)
        assert seek is not None and abs(seek['actual'] - seek['expected']) < .1, (frame, seek)
        page.wait_for_timeout(200)
        fingerprint = page.evaluate("""() => {
          const v = document.querySelector('#heroVideo');
          if (v.readyState < 2 || v.videoWidth < 1 || v.videoHeight < 1) return null;
          const c = document.createElement('canvas'); c.width = 64; c.height = 36;
          const ctx = c.getContext('2d'); ctx.drawImage(v, 0, 0, c.width, c.height);
          const data = ctx.getImageData(0, 0, c.width, c.height).data;
          let hash = 2166136261;
          for (let i = 0; i < data.length; i += 8) hash = Math.imul(hash ^ data[i], 16777619);
          return hash >>> 0;
        }""")
        assert fingerprint is not None, (frame, 'video frame unavailable')
        fingerprints.append(fingerprint)
        frame_image = screenshot(page)
        for item in evidence['items']:
            ratio = worst_sample(frame_image, item, evidence['viewport'])
            results.append({'frame': frame, 'group': item['group'], 'text': item['text'],
                            'ratio': ratio, 'minimum': item['minimum']})
    assert len(results) == 10 * len(evidence['items'])
    assert len(set(fingerprints)) >= 5, fingerprints
    minima = {group: min(r['ratio'] for r in results if r['group'] == group)
              for group in ('headline', 'eyebrow', 'fact', 'fact-label', 'action')}
    print(f'{theme} {w}x{h}: ' + json.dumps(minima, sort_keys=True))
    failures = [r for r in results if r['ratio'] < r['minimum']]
    if failures:
        pytest.fail(json.dumps(failures, ensure_ascii=False, indent=2), pytrace=False)


def test_contrast_sampler_rejects_white_text_on_white_hero(page_factory):
    """Negative control: a deliberately white hero must fail white headline ink."""
    page = page_factory(390, 844, mobile=True)
    page.wait_for_timeout(1800)
    evidence = targets(page)
    headline = next(x for x in evidence['items'] if x['group'] == 'headline')
    assert luminance(headline['rgb']) > .9, headline
    hide_text(page)
    page.add_style_tag(content='''
      #heroVideo, .hero__sky2, .hero__beams, .hero__spark {visibility:hidden !important}
      .hero__sky {background:white !important; opacity:1 !important; mix-blend-mode:normal !important}
      #heroCenter::before {display:none !important}
    ''')
    measured = worst_sample(screenshot(page), headline, evidence['viewport'])
    assert measured <= 1.05 and measured < headline['minimum'], measured


def test_contrast_targets_reject_transparent_text_fill(page_factory):
    """color може бути білим, але фактичний -webkit-text-fill — прозорим."""
    page = page_factory(390, 844, mobile=True, reduced=True)
    targets(page)
    page.add_style_tag(content='#heroTitle .w {-webkit-text-fill-color:transparent!important}')
    with pytest.raises(AssertionError):
        targets(page)
