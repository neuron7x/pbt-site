"""Контракт переносної збірки: оформлення не губиться після інлайнування."""

import ast
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess

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
    # Тестуємо семантику імпорту, а не крихкий порядок імен у рядку.
    imports = [
        {alias.name for alias in node.names}
        for node in ast.walk(ast.parse(code))
        if isinstance(node, ast.ImportFrom) and node.module == "bundle_contract"
    ]
    assert any({"emit_fragment", "inline_css"} <= names for names in imports)
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


@pytest.mark.parametrize("mode", ["live", "standalone", "multifile"])
def test_proof_cards_link_only_when_local_clips_are_distributed(mode):
    """Run the real renderer: a one-file export has no adjacent MP4 link targets.

    The DOM stub captures markup and observer registration; browser media and
    layout checks remain separate. No video assets or browser process required.
    """
    node = shutil.which("node")
    assert node, "Node.js is required to verify portable proof-card rendering"
    script = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const mode = process.argv[1];
const initial = {window: {}};
vm.runInNewContext(fs.readFileSync('web/js/data.js', 'utf8'), initial);
const D = initial.window.PBT;
if (mode === 'multifile') D.mp4Only = true;
if (mode === 'standalone') D.videoData = {'proof-amph.mp4': 'data:video/mp4;base64,AAAA'};
const source = fs.readFileSync('web/js/site.js', 'utf8');
const functions = ['httpsUrl', 'proofUrl', 'renderProof'].map(name => {
  const found = source.match(new RegExp('  function ' + name + '\\([^\\n]*\\) \\{[\\s\\S]*?\\n  \\}'));
  if (!found) throw new Error('Missing renderer dependency: ' + name);
  return found[0];
});
const esc = source.split('\n').find(line => line.trimStart().startsWith('const esc = '));
if (!esc) throw new Error('Missing shared HTML escaping');
const elements = {'#reel': {innerHTML: ''}, '#partners': {innerHTML: ''}};
const watched = [], selectors = [];
const context = {
  D, URL, window: {PBT_BUNDLE: mode !== 'live'},
  $: selector => elements[selector],
  $$: selector => {selectors.push(selector); return D.proof;},
  watchVideo: proof => watched.push(proof.video)
};
vm.runInNewContext(esc + '\n' + functions.join('\n') + '\nrenderProof();', context);
process.stdout.write(JSON.stringify({html: elements['#reel'].innerHTML, proof: D.proof, watched, selectors}));
"""
    run = subprocess.run([node, "-e", script, mode], cwd=ROOT,
                         capture_output=True, text=True, timeout=10, check=True)
    actual = json.loads(run.stdout)

    class Tags(HTMLParser):
        def __init__(self):
            super().__init__()
            self.nodes = []

        def handle_starttag(self, tag, attrs):
            self.nodes.append((tag, dict(attrs)))

    parsed = Tags()
    parsed.feed(actual["html"])
    cards = [(tag, attrs) for tag, attrs in parsed.nodes
             if "proof-card" in attrs.get("class", "").split()]
    assert len(cards) == len(actual["proof"]) == 6
    assert actual["selectors"] == ["#reel .proof-card"]
    assert actual["watched"] == [proof["video"] for proof in actual["proof"]]
    videos = [attrs for tag, attrs in parsed.nodes if tag == "video"]
    images = [attrs for tag, attrs in parsed.nodes if tag == "img"]
    assert [attrs["data-video"] for attrs in videos] == actual["watched"]
    assert [attrs["poster"] for attrs in videos] == [proof["poster"] for proof in actual["proof"]]
    assert len(images) == 6 and all(attrs.get("loading") == "lazy" for attrs in images)
    assert all("src" not in attrs for attrs in videos), "video sources must stay lazy"
    if mode == "standalone":
        assert all(tag == "article" and "href" not in attrs for tag, attrs in cards)
        assert not any(tag in ("a", "i") for tag, _ in parsed.nodes)
        assert all("відкрити відео" not in attrs.get("aria-label", "") for _, attrs in cards)
    else:
        assert all(tag == "a" and attrs.get("target") == "_blank" for tag, attrs in cards)
        assert [attrs["href"] for _, attrs in cards] == [proof["url"] for proof in actual["proof"]]
