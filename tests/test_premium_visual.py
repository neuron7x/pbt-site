"""Контраст нових текстових блоків: axe позначає градієнт incomplete."""
import re

import pytest


def luminance(rgb):
    values = [v / 255 for v in rgb]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
    return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))


def contrast(left, right):
    values = sorted((luminance(left), luminance(right)))
    return (values[1] + .05) / (values[0] + .05)


def test_contrast_oracle_rejects_previous_dark_on_deep_pairs():
    assert contrast((42, 82, 131), (10, 87, 194)) < 1.3
    assert contrast((67, 81, 94), (16, 24, 32)) < 2.3
    assert contrast((255, 255, 255), (10, 87, 194)) > 4.5


@pytest.mark.parametrize('theme', ['sky', 'precision'])
def test_request_content_contrast_on_every_gradient_stop(page_factory, theme):
    page = page_factory(reduced=True)
    page.locator(f'[data-theme-choice="{theme}"]').click()
    page.locator('.request-faq summary').first.click()
    samples = page.evaluate("""() => {
      const gradient = getComputedStyle(document.querySelector('#zapyt')).backgroundImage;
      return [...document.querySelectorAll('.request-steps .num,.request-steps p,.request-faq p')]
        .map(el => ({text: el.textContent, color: getComputedStyle(el).color, gradient}));
    }""")
    assert len(samples) == 9
    for sample in samples:
        foreground = tuple(map(int, re.findall(r'\d+', sample['color'])[:3]))
        stops = re.findall(r'rgb\((\d+), (\d+), (\d+)\)', sample['gradient'])
        assert len(stops) >= 2, sample
        for stop in stops:
            assert contrast(foreground, tuple(map(int, stop))) >= 4.5, sample
