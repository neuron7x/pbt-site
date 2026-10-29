#!/usr/bin/env python3
"""Відтворювані знімки ПБТ: реальні PNG, SHA-256, JSON-маніфест і fail-closed layout.

Запуск (з уже активним сервером):
    python tools/shots.py http://127.0.0.1:4180 [artifacts/shots]

Профіль зйомки: Chromium + prefers-reduced-motion. Це огляд статичного
інтерфейсу; анімований режим і Core Web Vitals потребують окремих перевірок.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from visual_contract import (
    SCHEMA_VERSION, THEMES, VIEWPORTS, audit_layout, capture_record, verify_capture_manifest,
)

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:4180"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("artifacts/shots")
OUT.mkdir(parents=True, exist_ok=True)

# Не прив'язуємо виміри до фіксованого CPU/4G — це діагностика локального
# запуску браузера, а НЕ 75-й процентиль польових Core Web Vitals.
PROBE = """() => {
  const displayed = el => {
    if (!el) return false;
    const b = el.getBoundingClientRect(), s = getComputedStyle(el);
    return b.width > 0 && b.height > 0 && s.display !== 'none' &&
      s.visibility !== 'hidden' && s.opacity !== '0';
  };
  const visibleBroken = [...document.images].filter(img => {
    const b = img.getBoundingClientRect();
    const onscreen = b.bottom > 0 && b.top < innerHeight &&
                     b.right > 0 && b.left < innerWidth;
    return onscreen && img.complete && !img.naturalWidth;
  }).map(img => img.getAttribute('src') || '[без src]');
  return {
    theme: document.documentElement.dataset.theme || null,
    appearance: {
      surface: getComputedStyle(document.body).backgroundColor,
      hero: getComputedStyle(document.getElementById('hero')).backgroundColor,
      heading_font: getComputedStyle(document.querySelector('h2')).fontFamily,
      cta_radius: getComputedStyle(document.querySelector('#hero .btn')).borderTopLeftRadius,
      pressed: [...document.querySelectorAll('[data-theme-choice][aria-pressed="true"]')]
        .map(el => el.dataset.themeChoice)
    },
    quality: document.documentElement.dataset.quality || null,
    visible_h1: displayed(document.querySelector('h1')),
    visible_cta: displayed(document.querySelector('#hero a[href="#zapyt"]')),
    horizontal_overflow: document.scrollingElement.scrollWidth > innerWidth + 1,
    sections: [...document.querySelectorAll('main section[id]')].map(el => el.id),
    broken_visible_images: visibleBroken,
    navigation: (() => {
      const e = performance.getEntriesByType('navigation')[0];
      return e ? {dom_content_loaded_ms: Math.round(e.domContentLoadedEventEnd),
                  load_event_ms: Math.round(e.loadEventEnd)} : null;
    })(),
    transfer_bytes_observed: performance.getEntriesByType('resource')
      .reduce((sum, item) => sum + (item.transferSize || 0), 0),
    // Без реальних взаємодій INP не вимірюється. CLS тут теж не є
    // 75-м процентилем сесій користувачів.
    field_cwv: null
  };
}"""


def capture_viewport(browser, spec: tuple, theme: str) -> tuple[dict, list[dict], list[str]]:
    key, width, height, mobile, scenes = spec
    context = browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=1,
        is_mobile=mobile,
        has_touch=mobile,
        reduced_motion="reduce",
        color_scheme="light",
        locale="uk-UA",
    )
    records = []
    violations = []
    if theme == "precision":
        # Ініціалізація до першого inline script/CSS: перевіряємо справжній restore.
        context.add_init_script("""try { localStorage.setItem('pbt-theme', 'precision'); } catch (_) {}""")
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda err: errors.append(str(err)[:350]))
    try:
        page.goto(BASE + "/", wait_until="networkidle", timeout=45000)
        page.evaluate("async () => { await document.fonts.ready; return true; }")
        page.wait_for_timeout(180)
        probe = page.evaluate(PROBE)
        probe["page_errors"] = list(errors)
        if probe["theme"] != theme:
            violations.append(f"{theme}/{key}: очікували тему {theme}, отримали {probe['theme']}")
        violations.extend(f"{theme}/{key}: {msg}" for msg in audit_layout(probe))
        for section in scenes:
            filename = f"{theme}--{key}--{section}.png"
            try:
                page.evaluate("""id => {
                  const el = document.getElementById(id);
                  if (!el) throw Error('Відсутня секція: ' + id);
                  el.scrollIntoView({block: 'start', behavior: 'instant'});
                }""", section)
                # Повний page.screenshot НЕ запускає lazy loading поза viewport.
                # Для кожного кадру очікуємо саме ВИДИМІ img і не приймаємо
                # порожню картку як візуальний доказ.
                page.wait_for_timeout(140)
                invalid_images = page.evaluate("""async () => {
                  const visible = [...document.images].filter(img => {
                    const b = img.getBoundingClientRect();
                    const style = getComputedStyle(img);
                    return b.width > 0 && b.height > 0 &&
                      style.display !== 'none' && style.visibility !== 'hidden' &&
                      b.right > 0 && b.left < innerWidth &&
                      b.bottom > 0 && b.top < innerHeight;
                  });
                  const results = await Promise.all(visible.map(async img => ({
                    img,
                    decoded: await Promise.race([
                      img.decode().then(() => true, () => false),
                      new Promise(resolve => setTimeout(() => resolve(false), 4000))
                    ])
                  })));
                  return results.filter(({img, decoded}) =>
                    !decoded || !img.complete || !img.naturalWidth)
                    .map(({img}) => img.currentSrc || img.getAttribute('src') || '[без src]');
                }""")
                if invalid_images:
                    violations.append(
                        f"{theme}/{key}/{section}: неготові видимі зображення: " +
                        ", ".join(invalid_images[:12])
                    )
                if page.evaluate("document.scrollingElement.scrollWidth > innerWidth + 1"):
                    violations.append(f"{theme}/{key}/{section}: горизонтальне переповнення")
                content = page.screenshot(
                    path=str(OUT / filename), animations="disabled",
                    caret="hide", scale="css", timeout=30000,
                )
                records.append(capture_record(content, filename, key, section, width, height, theme))
            except Exception as err:
                violations.append(f"{theme}/{key}/{section}: не створено PNG: {str(err)[:250]}")
        if errors:
            violations.extend(f"{theme}/{key}: JavaScript: {e}" for e in errors)
        return {
            "viewport": key, "theme": theme, "width": width, "height": height,
            "mobile": mobile, "profile": "reduced-motion / poster-only",
            "probe": probe,
        }, records, violations
    finally:
        context.close()


def run() -> int:
    report = {
        "schema_version": SCHEMA_VERSION,
        "revision": os.environ.get("PBT_HEAD_SHA") or os.environ.get("GITHUB_SHA") or None,
        "measurement_type": "laboratory screenshot audit; NOT field Core Web Vitals",
        "field_lcp_ms": None,
        "field_inp_ms": None,
        "field_cls": None,
        "browser": None,
        "viewports": [],
        "captures": [],
        "failures": [],
    }
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                report["browser"] = {"engine": "chromium", "version": browser.version}
                for theme in THEMES:
                    for spec in VIEWPORTS:
                        try:
                            profile, records, violations = capture_viewport(browser, spec, theme)
                            report["viewports"].append(profile)
                            report["captures"].extend(records)
                            report["failures"].extend(violations)
                        except Exception as exc:
                            report["failures"].append(f"{theme}/{spec[0]}: {type(exc).__name__}: {str(exc)[:350]}")
            finally:
                browser.close()
    except Exception as exc:
        report["failures"].append(f"Запуск браузера: {type(exc).__name__}: {str(exc)[:350]}")
    report["failures"].extend(verify_capture_manifest(report, OUT))
    (OUT / "manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Знімків: {len(report['captures'])}; браузер: {report['browser']}; "
          f"порушень: {len(report['failures'])}; маніфест: {OUT / 'manifest.json'}")
    for failure in report["failures"]:
        print("FAIL:", failure, file=sys.stderr)
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(run())
