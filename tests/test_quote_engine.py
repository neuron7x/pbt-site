"""Валідоване ядро кошторису: чистий оракул і parity з інтерфейсом."""
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
        [node, "--test", str(ROOT / "tests" / "quote_engine.test.cjs")],
        cwd=ROOT, text=True, capture_output=True, timeout=15, check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    assert "# fail 0" in run.stdout, run.stdout


def test_browser_quote_matches_single_ui_model(page_factory):
    page = page_factory(reduced=True)
    result = page.evaluate("""() => {
      const D = window.PBT, Q = window.PBTQuote;
      if (!Q || !Object.isFrozen(Q)) return null;
      return D.fleet.filter(u => u.price && u.unit === 'год')
        .flatMap(u => [0, 20, 40].map(km => {
          const q = Q.quote(u, D.trailers, 10, km);
          const legacy = window.PBTcalc(u.id, 10, km);
          const wanted = q === null ? null :
            q.status === 'complete' ? q.total :
            u.cat === 'crane' ? q.rental : null;
          return {id:u.id, km, legacy, wanted};
        }));
    }""")
    assert result and len(result) > 20
    assert all(row["legacy"] == row["wanted"] for row in result), result


def test_view_renders_partial_price_without_claiming_complete_delivery(page_factory):
    page = page_factory(reduced=True)
    page.select_option("#cMachine", "nav-1")  # no documented mass
    page.fill("#cHoursN", "2")
    page.dispatch_event("#cHoursN", "input")
    page.fill("#cKmN", "20")
    page.dispatch_event("#cKmN", "input")
    assert page.get_attribute("#cOut", "data-estimate") == "rent-only"
    assert page.get_attribute("#cOut", "data-total") == ""
    assert "маса невідома" in page.inner_text("#cLines")
    assert page.evaluate("window.PBTQuote.quote(window.PBT.fleet.find(u => u.id === 'nav-1'), window.PBT.trailers, 2, 20).total") is None


def test_single_runtime_dependency_is_in_every_build():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    build = (ROOT / "tools" / "inline.py").read_text(encoding="utf-8")
    loader = '<script src="js/quote.js"></script>'
    assert html.count(loader) == 1
    assert html.index(loader) < html.index('<script src="js/site.js"></script>')
    assert "quote = (WEB / 'js' / 'quote.js').read_text" in build
    assert build.count("'<script>' + quote + '</script>'") == 2
