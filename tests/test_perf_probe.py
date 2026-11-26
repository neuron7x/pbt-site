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
