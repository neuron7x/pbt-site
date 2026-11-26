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
from urllib.parse import urlsplit

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


def mobile_context(browser):
    return browser.new_context(
        viewport={"width": 390, "height": 844}, device_scale_factor=2,
        is_mobile=True, has_touch=True, reduced_motion="no-preference",
        locale="uk-UA",
    )


def theme_script(theme):
    return (
        "localStorage.setItem('pbt-theme', " + json.dumps(theme) + ");"
        "Object.defineProperty(navigator, 'hardwareConcurrency',"
        "{configurable:true,value:8});\n"
    )


def mobile_cdp(ctx, page):
    cdp = ctx.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Network.emulateNetworkConditions", {
        "offline": False, "latency": 150,
        "downloadThroughput": 200000, "uploadThroughput": 93750,
        "connectionType": "cellular4g",
    })
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    return cdp


def sample(browser, url: str, theme: str) -> dict:
    ctx = mobile_context(browser)
    try:
        ctx.add_init_script(theme_script(theme) + INSTRUMENT)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        mobile_cdp(ctx, page)
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


# Окрема навігація: прокрутка та збір мережевих подій не впливають на LCP/CLS.
MEDIA_FRAME_PROBE = r"""
(() => {
  const frame = window.__pbtHeroFrame = {status: 'hero_video_missing'};
  const observer = new MutationObserver(watch);
  function watch() {
    const video = document.getElementById('heroVideo');
    if (!(video instanceof HTMLVideoElement)) return;
    observer.disconnect();
    if (typeof video.requestVideoFrameCallback !== 'function') {
      frame.status = 'frame_callback_unsupported';
      return;
    }
    frame.status = 'frame_not_observed';
    video.requestVideoFrameCallback((now, metadata) => {
      frame.status = metadata.presentedFrames === 1 ? 'observed' : 'first_frame_missed';
      frame.presentation_ms = metadata.presentationTime;
      frame.expected_display_ms = metadata.expectedDisplayTime;
      frame.presented_frames = metadata.presentedFrames;
      frame.source = video.currentSrc;
    });
  }
  observer.observe(document, {childList: true, subtree: true});
  watch();
})();
"""


def media_path(value, page_url):
    asset, page = urlsplit(value), urlsplit(page_url)
    if ((asset.scheme, asset.netloc) == (page.scheme, page.netloc)
            and not asset.query and asset.path.endswith((".mp4", ".webm"))):
        return asset.path
    return None


def navigation_start(metrics, before_ms, after_ms):
    """Звірити, що Chrome TimeTicks і DOMHighResTimeStamp описують ту саму навігацію."""
    values = {item["name"]: item["value"] for item in metrics}
    start, current = values.get("NavigationStart"), values.get("Timestamp")
    if start is not None and current is not None and math.isfinite(start) and start > 0:
        elapsed = (current - start) * 1000
        if before_ms - 1 <= elapsed <= after_ms + 1:
            return start
    return None


def network_checkpoint(chunks, start, cutoff_ms, *, strict=False):
    if cutoff_ms is None:
        return {"status": "checkpoint_unavailable", "at_ms": None, "encoded_bytes_by_path": None}
    if start is None:
        return {"status": "clock_unavailable", "at_ms": cutoff_ms, "encoded_bytes_by_path": None}
    cutoff = start + cutoff_ms / 1000
    totals = {}
    for timestamp, path, encoded_bytes in chunks:
        if start <= timestamp and (timestamp < cutoff if strict else timestamp <= cutoff):
            totals[path] = totals.get(path, 0) + encoded_bytes
    return {"status": "observed", "at_ms": cutoff_ms, "encoded_bytes_by_path": totals}


def wait_for_page_time(page, target_ms, limit_ms):
    """Wait on the Playwright side so the page keeps its production CSP."""
    left = target_ms - page.evaluate("performance.now()")
    if not math.isfinite(left) or left > limit_ms:
        raise RuntimeError("Мережева проба не може дочекатися часової межі")
    if left > 0:
        page.wait_for_timeout(math.ceil(left))
    if page.evaluate("performance.now()") < target_ms:
        raise RuntimeError("Мережева проба зупинилась до часової межі")


def sample_media_network(browser, url, theme):
    ctx = mobile_context(browser)
    try:
        ctx.add_init_script(theme_script(theme) + MEDIA_FRAME_PROBE)
        page = ctx.new_page()
        media_paths, chunks = {}, []
        cdp = mobile_cdp(ctx, page)

        def request(event):
            request_id = event["requestId"]
            path = media_path(event["request"]["url"], url)
            if path is None:
                media_paths.pop(request_id, None)
            else:
                media_paths[request_id] = path

        def received(event):
            path = media_paths.get(event["requestId"])
            if path is not None:
                chunks.append((event["timestamp"], path, event["encodedDataLength"]))

        cdp.on("Network.requestWillBeSent", request)
        cdp.on("Network.dataReceived", received)
        cdp.send("Performance.enable", {"timeDomain": "timeTicks"})
        response = page.goto(url, wait_until="load", timeout=45000)
        if not response or response.status != 200:
            raise RuntimeError("Мережева проба не отримала HTTP 200")
        if page.evaluate("document.documentElement.dataset.theme") != theme:
            raise RuntimeError("Мережева проба отримала іншу тему")

        before = page.evaluate("performance.now()")
        metrics = cdp.send("Performance.getMetrics")["metrics"]
        after = page.evaluate("performance.now()")
        start = navigation_start(metrics, before, after)

        wait_for_page_time(page, 5000, 6000)
        scroll = page.evaluate("""(() => {
          const from_y = scrollY;
          const at_ms = performance.now();
          window.scrollTo({top: from_y + innerHeight, behavior: 'instant'});
          return {from_y, to_y: scrollY, requested_delta_px: innerHeight, at_ms};
        })()""")
        applied = scroll["to_y"] > scroll["from_y"]
        observed_after_scroll = scroll["at_ms"] + 1000 if applied else None
        if applied:
            wait_for_page_time(page, observed_after_scroll, 3000)

        frame = page.evaluate("window.__pbtHeroFrame")
        frame["source_path"] = media_path(frame.pop("source", ""), url)
        first_cutoff = frame.get("presentation_ms") if frame["status"] == "observed" else None
        return {
            "metric": "cdp_data_received_encoded_bytes_for_same_origin_queryless_video",
            "network_clock": "chromium_navigation_start" if start is not None else "unavailable",
            "hero_frame": frame,
            "scroll": {**scroll, "applied": applied},
            "before_first_composited_frame": network_checkpoint(chunks, start, first_cutoff, strict=True),
            "through_5_seconds": network_checkpoint(chunks, start, 5000),
            "through_1_second_after_scroll": network_checkpoint(chunks, start, observed_after_scroll),
        }
    finally:
        ctx.close()


def run(url: str, repetitions: int, *, media_network: bool = False) -> dict:
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
            network = ({theme: sample_media_network(browser, url, theme) for theme in THEMES}
                       if media_network else None)
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
        **({"media_network_diagnostics": network} if network is not None else {}),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="http://127.0.0.1:4180/")
    ap.add_argument("--out", default="artifacts/perf/dual-theme-mobile.json")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--media-network", action="store_true",
                    help="Окрема навігація на тему для таймлайна мережевих байтів відео")
    args = ap.parse_args()
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = run(args.url, args.runs, media_network=args.media_network)
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
