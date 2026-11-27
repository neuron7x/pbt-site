"""Валідоване ядро кошторису: історичний чистий оракул і межа публічної вітрини."""
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_node_quote_kernel_property_suite():
    # CI already requires Node for node --check, so an absent runtime is a
    # failing prerequisite, not an excuse to silently skip the core model.
    node = shutil.which("node")
    assert node, "Node.js >=20 is required to verify the quote model"
    run = subprocess.run(
        [node, "--test", "--test-reporter=tap", str(ROOT / "tests" / "quote_engine.test.cjs")],
        cwd=ROOT, text=True, capture_output=True, timeout=15, check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    assert "# fail 0" in run.stdout, run.stdout


def test_quote_kernel_is_excluded_from_live_and_offline_loaders():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    build = (ROOT / "tools" / "inline.py").read_text(encoding="utf-8")
    assert 'js/quote.js' not in html
    assert 'js/quote.js' not in build and "'quote.js'" not in build


def test_public_runtime_does_not_attach_the_archival_quote_api(page_factory):
    page = page_factory(reduced=True)
    assert page.evaluate("typeof window.PBTQuote") == "undefined"
    assert page.evaluate("typeof window.PBTcalc") == "undefined"
