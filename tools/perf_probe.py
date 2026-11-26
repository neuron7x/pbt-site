#!/usr/bin/env python3
"""Synthetic 2026 mobile Web Vitals evidence, never a field/INP certification.

Two independent theme configurations; three isolated Chromium navigations
each, reproducible CPU and network throttling, raw observations in JSON.
Synthetic metrics alone do not authorize a merge or production deployment.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def source_identity() -> dict:
    """The tested checkout, not the GitHub PR's synthetic event merge ref."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=ROOT, check=True, capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("unable to verify checked-out git revision") from exc
    actual = result.stdout.strip()
    if len(actual) != 40 or any(char not in "0123456789abcdef" for char in actual):
        raise RuntimeError("invalid checked-out commit SHA")
    expected = os.getenv("PBT_HEAD_SHA")
    if expected is not None and actual != expected:
        raise RuntimeError("checked-out revision differs from PBT_HEAD_SHA")
    return {
        "execution_sha": actual,
        "branch_head_sha": expected,
        "event_sha": os.getenv("GITHUB_SHA"),
    }


THEMES = ("sky", "precision")
LCP_LIMIT_MS = 2500.0
CLS_LIMIT = 0.1
INSTRUMENT = r"""
(() => {
  const nodeLabel = node => {
    if (!node) return 'unknown';
    // LayoutShiftAttribution.node may be Document or Text, not Element.
    const raw = typeof node.tagName === 'string' ? node.tagName :
      (typeof node.nodeName === 'string' ? node.nodeName : 'unknown');
    const id = typeof node.id === 'string' && node.id ? '#' + node.id : '';
    const classes = node.classList && node.classList.length
      ? '.' + Array.from(node.classList).slice(0, 2).join('.') : '';
    return raw.toLowerCase() + id + classes;
  };
  const lcpElement = element => {
    if (!(element instanceof Element)) return 'unavailable';
    if (element.closest('#heroVideo')) return 'hero-video';
    if (element.closest('.logo-hero')) return 'hero-logo';
    if (element.closest('#heroTitle')) return 'hero-title';
    if (element.closest('#hero')) return 'hero-other';
    return 'other';
  };
  const vitals = window.__pbtVitals = {
    observers: {}, lcp: null, lcpElement: null, lcpCandidates: [], shifts: [], longTasks: 0, nodeLabel
  };
  const observe = (type, callback) => {
    if (typeof PerformanceObserver !== 'function' ||
        !PerformanceObserver.supportedEntryTypes?.includes(type)) {
      vitals.observers[type] = 'unsupported';
      return;
    }
    try {
      new PerformanceObserver(callback).observe({type, buffered: true});
      vitals.observers[type] = 'registered';
    } catch (_) {
      vitals.observers[type] = 'registration_failed';
    }
  };
  observe('largest-contentful-paint', list => {
    for (const e of list.getEntries()) {
      vitals.lcp = e.startTime;
      vitals.lcpElement = lcpElement(e.element);
      vitals.lcpCandidates.push({
        element: vitals.lcpElement, start_ms: e.startTime, render_ms: e.renderTime || null
      });
    }
  });
  observe('layout-shift', list => {
    for (const e of list.getEntries()) vitals.shifts.push({
      start: e.startTime, value: e.value, hadRecentInput: e.hadRecentInput,
      sources: (e.sources || []).slice(0, 6).map(s => {
        return {element: nodeLabel(s.node),
          beforeY: s.previousRect?.y ?? null,
          afterY: s.currentRect?.y ?? null};
      })
    });
  });
  observe('longtask', list => {
    vitals.longTasks += list.getEntries().length;
  });
})();
"""


def p75(values: list[float]) -> float:
    """Noninterpolated nearest-rank 75th percentile."""
    if len(values) < 3 or any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("p75 requires at least three finite, nonnegative values")
    v = sorted(values)
    return v[math.ceil(len(v) * 0.75) - 1]


def cls_max_session(entries: list[dict]) -> float:
    """Standard CLS: exclude input-related shifts; <=1s gaps, <=5s windows."""
    entries = sorted((float(e["start"]), float(e["value"]))
                     for e in entries if not e["hadRecentInput"])
    start = last = None
    total = maximum = 0.0
    for timestamp, value in entries:
        if start is None or timestamp - last > 1000 or timestamp - start > 5000:
            start, total = timestamp, value
        else:
            total += value
        last = timestamp
        maximum = max(maximum, total)
    return maximum


def sample(browser, url: str, theme: str) -> dict:
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844}, device_scale_factor=2,
        is_mobile=True, has_touch=True, reduced_motion="no-preference",
        locale="uk-UA",
    )
    try:
        ctx.add_init_script(
            "localStorage.setItem('pbt-theme', " + json.dumps(theme) + ");"
            "Object.defineProperty(navigator, 'hardwareConcurrency',"
            "{configurable:true,value:8});\n" + INSTRUMENT
        )
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        cdp = ctx.new_cdp_session(page)
        cdp.send("Network.enable")
        cdp.send("Network.emulateNetworkConditions", {
            "offline": False, "latency": 150,
            "downloadThroughput": 200000, "uploadThroughput": 93750,
            "connectionType": "cellular4g",
        })
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
        response = page.goto(url, wait_until="load", timeout=45000)
        page.wait_for_timeout(3500)
        first = page.evaluate("""() => ({
          theme: document.documentElement.dataset.theme,
          lcp: window.__pbtVitals?.lcp ?? null,
          lcpElement: window.__pbtVitals?.lcpElement ?? null,
          lcpCandidates: window.__pbtVitals?.lcpCandidates ?? [],
          observers: window.__pbtVitals?.observers ?? {},
          shifts: window.__pbtVitals?.shifts ?? null,
          longTasks: window.__pbtVitals?.longTasks ?? null,
          bytes: performance.getEntriesByType('resource')
            .reduce((total, e) => total + (e.transferSize || 0), 0)
        })""")
        if not response or response.status != 200:
            raise RuntimeError("probe did not receive HTTP 200")
        for entry_type in ("largest-contentful-paint", "layout-shift"):
            status = first["observers"].get(entry_type, "missing")
            if status != "registered":
                raise RuntimeError(f"{entry_type} observer for {theme}: {status}")
        if first["theme"] != theme:
            raise RuntimeError("prepaint theme missing for " + theme)
        if first["lcp"] is None or first["shifts"] is None:
            raise RuntimeError("required performance observations missing for " + theme)
        if errors:
            raise RuntimeError("JavaScript exception: " + errors[0])
        stamp = page.evaluate("performance.now()")
        alternate = "precision" if theme == "sky" else "sky"
        page.locator('[data-theme-choice="' + alternate + '"]').click()
        page.wait_for_timeout(700)
        all_shifts = page.evaluate("window.__pbtVitals.shifts")
        induced = [e for e in all_shifts if e["start"] >= stamp]
        if page.evaluate("document.documentElement.dataset.theme") != alternate:
            raise RuntimeError("theme switch failed")
        if errors:
            raise RuntimeError("JavaScript exception during switch: " + errors[0])
        return {
            "theme": theme, "lcp_ms": round(float(first["lcp"]), 2),
            "lcp_element": first["lcpElement"],
            "lcp_candidates": first["lcpCandidates"],
            "cls": round(cls_max_session(first["shifts"]), 5),
            "observers": first["observers"],
            "long_tasks": (first["longTasks"]
                           if first["observers"].get("longtask") == "registered"
                           else None),
            "resource_transfer_bytes": first["bytes"],
            "switch_all_shift_sum": round(sum(e["value"] for e in induced), 5),
            "switch_unprompted_shift_sum": round(
                sum(e["value"] for e in induced if not e["hadRecentInput"]), 5),
            "switch_shift_events": len(induced),
            "switch_shifts": induced,
        }
    finally:
        ctx.close()


def run(url: str, repetitions: int) -> dict:
    if repetitions < 3:
        raise ValueError("at least three runs per theme required")
    identity = source_identity()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            chromium_version = browser.version
            samples = {
                theme: [sample(browser, url, theme) for _ in range(repetitions)]
                for theme in THEMES
            }
        finally:
            browser.close()
    summaries = {}
    for theme, raw in samples.items():
        lcp = p75([s["lcp_ms"] for s in raw])
        cls = p75([s["cls"] for s in raw])
        max_deferred_shift = max(s["switch_unprompted_shift_sum"] for s in raw)
        summaries[theme] = {
            "p75_lcp_ms": lcp, "p75_cls": cls,
            "max_deferred_switch_shift": max_deferred_shift,
            "synthetic_budget_met": lcp <= LCP_LIMIT_MS and cls <= CLS_LIMIT,
            "switch_stable": max_deferred_shift <= 0.001,
            "raw": raw,
        }
    return {
        "schema_version": 3, **identity,
        "kind": "synthetic_chromium_lab_not_field_data",
        "profile": {"chromium_version": chromium_version, "width": 390, "height": 844, "dpr": 2,
                    "cpu_throttle": 4, "logical_cores_override": 8,
                    "latency_ms": 150, "down_bytes_per_sec": 200000,
                    "runs_per_theme": repetitions},
        "budgets": {"lcp_ms": LCP_LIMIT_MS, "cls": CLS_LIMIT, "inp_ms": 200},
        "inp_ms": None, "field_vitals_verified": False,
        "release_status": "UNVERIFIED_FIELD_INP_AND_VISUAL_ACCEPTANCE",
        "themes": summaries,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="http://127.0.0.1:4180/")
    ap.add_argument("--out", default="artifacts/perf/dual-theme-mobile.json")
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = run(args.url, args.runs)
    except Exception as exc:
        # Preserve failed-run evidence; still fail CI and retain the traceback.
        failure = {
            "schema_version": 3,
            "kind": "synthetic_chromium_lab_not_field_data",
            "release_status": "MEASUREMENT_FAILED",
            "execution_sha": None,
            "branch_head_sha": os.getenv("PBT_HEAD_SHA"),
            "event_sha": os.getenv("GITHUB_SHA"),
            "error_class": type(exc).__name__, "error": str(exc),
            "field_vitals_verified": False, "inp_ms": None,
        }
        output.write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")
        raise
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    for theme, metrics in result["themes"].items():
        print(theme, "synthetic p75 LCP=", metrics["p75_lcp_ms"],
              "CLS=", metrics["p75_cls"],
              "LAB_BUDGET_MET=", metrics["synthetic_budget_met"],
              "SWITCH_STABLE=", metrics["switch_stable"],
              "DEFERRED_SHIFT=", metrics["max_deferred_switch_shift"])
    print("INP=NOT_MEASURED; FIELD_METRICS=UNVERIFIED; artifact=", output)
    return 0 if all(
        metrics["synthetic_budget_met"] and metrics["switch_stable"]
        for metrics in result["themes"].values()
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
