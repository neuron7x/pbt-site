"""Unit proof for the numerical methodology of the synthetic mobile probe."""
import pytest

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
