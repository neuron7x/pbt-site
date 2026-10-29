"""Контракт переносної збірки: оформлення не губиться після інлайнування."""

from pathlib import Path

import pytest

from tools.bundle_contract import emit_fragment, inline_css

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


def test_inline_css_preserves_stylesheet_order_and_removes_external_links():
    doc = '<head>' + ''.join(
        f'<link rel="stylesheet" href="{p}">'
        for p in ("css/fonts.css", "css/site.css")
    ) + "</head>"
    res = inline_css(doc, (
        ("css/fonts.css", "/* шрифти */"),
        ("css/site.css", "/* обидві теми */"),
    ))
    assert res.count("<style>") == 2
    assert res.index("/* шрифти */") < res.index("/* обидві теми */")
    assert "rel=\"stylesheet\"" not in res


@pytest.mark.parametrize("doc", [
    '<link rel="stylesheet" href="css/site.css"><link rel="stylesheet" href="css/site.css">',
    "<main>без CSS</main>",
])
def test_inline_css_fails_on_duplicate_or_missing_link(doc):
    with pytest.raises(ValueError):
        inline_css(doc, (("css/site.css", "body{}"),))


def test_inline_css_fails_on_unapproved_extra_stylesheet():
    doc = '<link rel="stylesheet" href="css/site.css"><link rel="stylesheet" href="css/unknown.css">'
    with pytest.raises(ValueError, match="зовнішнє"):
        inline_css(doc, (("css/site.css", "body{}"),))


def test_actual_offline_input_embeds_single_canonical_dual_theme_stylesheet():
    source = (WEB / "index.html").read_text(encoding="utf-8")
    styles = tuple(
        (path, (WEB / path).read_text(encoding="utf-8"))
        for path in ("css/fonts.css", "css/site.css")
    )
    html = inline_css(source, styles)
    assert "css/precision.css" not in html
    assert ':root[data-theme="precision"]' in html
    assert ':root[data-theme="sky"]' in html
    assert "css/site.css" not in html
    assert html.count("<style>") == 2
    assert html.index(styles[0][1][:80]) < html.index(styles[1][1][:80])


def test_inline_builder_uses_shared_contract_for_both_outputs():
    code = (ROOT / "tools" / "inline.py").read_text(encoding="utf-8")
    assert "from bundle_contract import inline_css" in code
    assert code.count("inline_css(") == 2  # однофайлова й багатофайлова
    assert code.count("emit_fragment(") == 2  # обидва артефакти: prepaint перед CSS


def test_portable_fragments_restore_theme_before_any_stylesheet():
    prepaint = '<script>document.documentElement.dataset.theme="precision"</script>'
    head_items = ['<meta name="description" content="test">',
                  '<style>body{color:#fff}</style>', '<style>body{margin:0}</style>']
    result = emit_fragment("Theme contract", head_items, prepaint, "<main>ok</main>")
    assert result.index("dataset.theme") < result.index("<style>")
    assert result.count("<style>") == 2
    assert result.endswith("<main>ok</main>")


@pytest.mark.parametrize("prepaint,head", [
    ("", ["<style>body{}</style>"]),
    ("<script>alert(1)</script>", ["<style>body{}</style>"]),
    ('<script>document.documentElement.dataset.theme="sky"</script>',
     ['<link rel="stylesheet" href="css/site.css">']),
])
def test_portable_fragment_fails_closed_without_safe_prepaint(prepaint, head):
    with pytest.raises(ValueError):
        emit_fragment("Title", head, prepaint, "<main></main>")
