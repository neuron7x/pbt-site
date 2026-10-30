"""Chromium/WebKit parity over the same quote kernel and theme runtime.

No new prices, network fixtures or snapshots: assert identical business
contracts across both real browser engines, including persistent theme state.
"""
import pytest


@pytest.mark.parametrize("engine", ("chromium", "webkit"))
def test_quote_kernel_and_theme_parity_across_browser_engines(pw, server, engine):
    browser = getattr(pw, engine).launch()
    context = browser.new_context(viewport={"width": 390, "height": 844}, reduced_motion="reduce")
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    try:
        response = page.goto(server["base"] + "/", wait_until="networkidle", timeout=45000)
        assert response and response.status == 200
        rows = page.evaluate("""() => {
          const D = window.PBT, Q = window.PBTQuote;
          if (!D || !Q || typeof window.PBTcalc !== 'function') return null;
          return D.fleet.filter(u => Number.isSafeInteger(u.price) && u.price > 0 && u.unit === 'год')
            .flatMap(u => [0, 20, 40].map(km => {
              const q = Q.quote(u, D.trailers, 10, km);
              const expected = q === null ? null :
                q.status === 'complete' ? q.total :
                u.cat === 'crane' ? q.rental : null;
              return {id: u.id, km, expected, actual: window.PBTcalc(u.id, 10, km)};
            }));
        }""")
        assert rows and len(rows) >= 24, (engine, rows)
        assert all(row["expected"] == row["actual"] for row in rows), (engine, rows)
        page.locator('[data-theme-choice="precision"]').click()
        assert page.evaluate("document.documentElement.dataset.theme") == "precision"
        page.reload(wait_until="networkidle", timeout=45000)
        assert page.evaluate("document.documentElement.dataset.theme") == "precision"
        assert not errors, (engine, errors)
    finally:
        context.close()
        browser.close()
