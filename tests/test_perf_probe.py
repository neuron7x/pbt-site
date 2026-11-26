"""Unit proof for the numerical methodology of the synthetic mobile probe."""
import pytest

from tools import perf_probe
from tools.perf_probe import INSTRUMENT, cls_max_session, p75


def test_p75_is_nearest_rank_not_interpolated():
    assert p75([200, 100, 300]) == 300
    assert p75([10, 20, 30, 40]) == 30


@pytest.mark.parametrize("values", [[], [1, 2], [-1, 2, 3],
                                    [1, 2, float("nan")],
                                    [1, 2, float("inf")]])
def test_p75_rejects_invalid_or_insufficient_evidence(values):
    with pytest.raises(ValueError):
        p75(values)


def test_cls_uses_session_windows_and_excludes_recent_input():
    entries = [
        {"start": 100, "value": 0.02, "hadRecentInput": False},
        {"start": 500, "value": 0.03, "hadRecentInput": False},
        {"start": 700, "value": 0.25, "hadRecentInput": True},
        {"start": 2500, "value": 0.04, "hadRecentInput": False},
        {"start": 3400, "value": 0.02, "hadRecentInput": False},
    ]
    assert cls_max_session(entries) == pytest.approx(0.06)


def test_cls_resets_if_a_session_exceeds_five_seconds():
    entries = [{"start": i * 900, "value": 0.02, "hadRecentInput": False}
               for i in range(7)]
    assert cls_max_session(entries) == pytest.approx(0.12)


def test_only_input_related_shifts_do_not_contribute_to_standard_cls():
    assert cls_max_session([{"start": 250, "value": 0.8,
                             "hadRecentInput": True}]) == 0.0



def test_shift_source_label_handles_document_text_and_svg_nodes(browser):
    """Real Chromium regression for the 2026-10-29 probe crash on non-Element nodes."""
    page = browser.new_page()
    try:
        page.goto("about:blank")
        page.evaluate(INSTRUMENT)
        labels = page.evaluate("""() => {
          const div = document.createElement('div');
          div.id = 'target';
          div.className = 'one two';
          const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
          return [
            window.__pbtVitals.nodeLabel(document),
            window.__pbtVitals.nodeLabel(document.createTextNode('text')),
            window.__pbtVitals.nodeLabel(div),
            window.__pbtVitals.nodeLabel(svg),
            window.__pbtVitals.nodeLabel(null)
          ];
        }""")
        assert labels == ["#document", "#text", "div#target.one.two", "svg", "unknown"]
    finally:
        page.close()


@pytest.fixture
def observer_probe(browser, monkeypatch):
    """Measure a static in-memory page through the production sample path."""
    from json import dumps
    from types import SimpleNamespace

    url = "http://127.0.0.1:8000/"
    html = """<!doctype html><meta name="viewport" content="width=device-width">
      <script>document.documentElement.dataset.theme = localStorage.getItem('pbt-theme')</script>
      <h1 id="heroTitle">Контрольний заголовок</h1>
      <button data-theme-choice="precision"
        onclick="document.documentElement.dataset.theme = 'precision'">Графіт</button>"""

    def new_context(**options):
        context = browser.new_context(**options)
        context.route(url, lambda route: route.fulfill(content_type="text/html", body=html))
        return context

    def run(disabled_type, operation):
        monkeypatch.setattr(perf_probe, "INSTRUMENT", f"""
            (() => {{
              const NativeObserver = window.PerformanceObserver;
              const type = {dumps(disabled_type)};
              const operation = {dumps(operation)};
              window.PerformanceObserver = class extends NativeObserver {{
                static get supportedEntryTypes() {{
                  return NativeObserver.supportedEntryTypes.filter(
                    entry => operation !== 'unsupported' || entry !== type);
                }}
                observe(options) {{
                  if (operation === 'throws' && options.type === type)
                    throw new DOMException('injected observer failure');
                  super.observe(options);
                }}
              }};
            }})();
            """ + INSTRUMENT)
        return perf_probe.sample(SimpleNamespace(new_context=new_context), url, "sky")

    return run


@pytest.mark.parametrize("entry_type,operation", [
    ("layout-shift", "unsupported"), ("layout-shift", "throws"),
    ("largest-contentful-paint", "unsupported"),
])
def test_sample_rejects_required_observer_failure(observer_probe, entry_type, operation):
    with pytest.raises(RuntimeError, match=entry_type):
        observer_probe(entry_type, operation)


def test_sample_reports_zero_cls_from_a_registered_observer(observer_probe):
    result = observer_probe("longtask", "throws")
    assert result["observers"] == {
        "largest-contentful-paint": "registered",
        "layout-shift": "registered",
        "longtask": "registration_failed",
    }
    assert result["cls"] == 0.0
    assert result["long_tasks"] is None
    assert result["lcp_element"] == "hero-title"
    candidates = result["lcp_candidates"]
    assert candidates
    assert candidates[-1]["element"] == result["lcp_element"]
    assert candidates[-1]["start_ms"] == pytest.approx(result["lcp_ms"], abs=0.0051)
    assert all(entry["render_ms"] is None or entry["render_ms"] > 0 for entry in candidates)


def test_source_identity_records_checked_out_head_not_event_merge_sha(monkeypatch):
    from subprocess import CompletedProcess
    from tools import perf_probe
    actual, event = "a" * 40, "b" * 40
    monkeypatch.setenv("PBT_HEAD_SHA", actual)
    monkeypatch.setenv("GITHUB_SHA", event)
    monkeypatch.setattr(perf_probe.subprocess, "run", lambda *a, **kw:
                        CompletedProcess(a, 0, stdout=actual + "\n"))
    identity = perf_probe.source_identity()
    assert identity == {"execution_sha": actual,
                        "branch_head_sha": actual, "event_sha": event}


def test_source_identity_rejects_checkout_head_mismatch_and_fake_sha(monkeypatch):
    from subprocess import CompletedProcess
    from tools import perf_probe
    monkeypatch.setenv("PBT_HEAD_SHA", "a" * 40)
    monkeypatch.setattr(perf_probe.subprocess, "run", lambda *a, **kw:
                        CompletedProcess(a, 0, stdout="b" * 40 + "\n"))
    with pytest.raises(RuntimeError, match="differs from PBT_HEAD_SHA"):
        perf_probe.source_identity()
    monkeypatch.setattr(perf_probe.subprocess, "run", lambda *a, **kw:
                        CompletedProcess(a, 0, stdout="not-a-sha\n"))
    with pytest.raises(RuntimeError, match="invalid checked-out commit SHA"):
        perf_probe.source_identity()



def test_network_checkpoint_keeps_url_and_time_boundaries():
    assert hasattr(perf_probe, "network_checkpoint")
    chunks = [
        (79.9, "/media/previous.mp4", 500),
        (80.03, "/media/hero-tall.webm", 11),
        (80.1, "/media/hero-tall.webm", 20),
        (80.2, "/media/hero-tall.webm", 30),
        (84.0, "/media/other.mp4", 100),
        (85.0, "/media/hero-tall.webm", 40),
        (85.001, "/media/other.mp4", 25),
        (86.2, "/media/other.mp4", 90),
    ]
    before = perf_probe.network_checkpoint(chunks, 80.0, 100, strict=True)
    five = perf_probe.network_checkpoint(chunks, 80.0, 5000)
    after = perf_probe.network_checkpoint(chunks, 80.0, 6100)
    assert before["encoded_bytes_by_path"] == {"/media/hero-tall.webm": 11}
    assert five["encoded_bytes_by_path"] == {"/media/hero-tall.webm": 101, "/media/other.mp4": 100}
    assert after["encoded_bytes_by_path"] == {"/media/hero-tall.webm": 101, "/media/other.mp4": 125}


def test_unavailable_checkpoints_never_become_zero_byte_samples():
    assert hasattr(perf_probe, "network_checkpoint")
    missing_frame = perf_probe.network_checkpoint([], 80.0, None)
    missing_clock = perf_probe.network_checkpoint([], None, 5000)
    no_chunks = perf_probe.network_checkpoint([], 80.0, 5000)
    assert missing_frame["status"] == "checkpoint_unavailable"
    assert missing_clock["status"] == "clock_unavailable"
    assert missing_frame["encoded_bytes_by_path"] is None
    assert missing_clock["encoded_bytes_by_path"] is None
    assert no_chunks["encoded_bytes_by_path"] == {}


def test_clock_mismatch_invalidates_byte_cutoffs():
    assert hasattr(perf_probe, "navigation_start")
    metrics = [{"name": "NavigationStart", "value": 80.0},
               {"name": "Timestamp", "value": 85.005}]
    assert perf_probe.navigation_start(metrics, 5004, 5006) == 80.0
    assert perf_probe.navigation_start(metrics, 1004, 1006) is None
    assert perf_probe.navigation_start(metrics[1:], 5004, 5006) is None


def test_network_clock_matches_real_chromium_navigation(browser):
    assert hasattr(perf_probe, "navigation_start")
    page = browser.new_page()
    try:
        cdp = page.context.new_cdp_session(page)
        cdp.send("Performance.enable", {"timeDomain": "timeTicks"})
        page.goto("data:text/html,<title>Мережева проба</title>")
        before = page.evaluate("performance.now()")
        metrics = cdp.send("Performance.getMetrics")["metrics"]
        after = page.evaluate("performance.now()")
        assert perf_probe.navigation_start(metrics, before, after) is not None
    finally:
        page.close()



def test_hero_frame_probe_records_chromium_composition_time(browser):
    assert hasattr(perf_probe, "MEDIA_FRAME_PROBE")
    page = browser.new_page()
    try:
        page.goto("data:text/html,<title>Мережева проба</title>")
        page.evaluate(perf_probe.MEDIA_FRAME_PROBE)
        page.evaluate("""(() => {
          const video = document.createElement('video');
          video.id = 'heroVideo';
          video.muted = true;
          document.body.append(video);
          const canvas = document.createElement('canvas');
          canvas.width = canvas.height = 20;
          const context = canvas.getContext('2d');
          const stream = canvas.captureStream(0);
          const [track] = stream.getVideoTracks();
          video.srcObject = stream;
          video.play().catch(error => { window.__pbtFrameTestError = String(error); });
          let red = false;
          const draw = () => {
            context.fillStyle = red ? 'red' : 'blue';
            context.fillRect(0, 0, 20, 20);
            track.requestFrame();
            red = !red;
          };
          draw();
          setInterval(draw, 40);
        })()""")
        page.wait_for_function(
            "() => window.__pbtFrameTestError || "
            "['observed','first_frame_missed'].includes(window.__pbtHeroFrame.status)",
            timeout=5000,
        )
        assert page.evaluate("window.__pbtFrameTestError") is None
        frame = page.evaluate("window.__pbtHeroFrame")
        assert frame["status"] == "observed"
        assert frame["presented_frames"] == 1
        assert 0 <= frame["presentation_ms"] <= frame["expected_display_ms"]
    finally:
        page.close()


def test_media_network_checkpoints_preserve_strict_csp(browser):
    from types import SimpleNamespace

    assert hasattr(perf_probe, "sample_media_network")
    base = "http://127.0.0.1:8000/"
    html = ("<!doctype html><script src='/boot.js'></script><main>"
            + "<p>Перевірка прокрутки</p>" * 100 + "</main>")

    def new_context(**options):
        ctx = browser.new_context(**options)
        ctx.route(base, lambda route: route.fulfill(
            content_type="text/html", body=html,
            headers={"Content-Security-Policy": "script-src 'self'"}))
        ctx.route(base + "boot.js", lambda route: route.fulfill(
            content_type="application/javascript",
            body="document.documentElement.dataset.theme = localStorage.getItem('pbt-theme')"))
        return ctx

    result = perf_probe.sample_media_network(SimpleNamespace(new_context=new_context), base, "sky")
    assert result["hero_frame"]["status"] == "hero_video_missing"
    assert result["scroll"]["applied"]
    assert result["through_5_seconds"]["at_ms"] == 5000
    assert result["through_1_second_after_scroll"]["at_ms"] >= 6000
