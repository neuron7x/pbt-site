"""Chromium/WebKit parity over the same quote kernel and theme runtime.

No new prices, network fixtures or snapshots: assert identical business
contracts across both real browser engines, including persistent theme state.
"""
from time import monotonic
import json

import pytest


def parity_rows(page):
    return page.evaluate("""() => {
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


def assert_parity_rows(engine, rows, diagnostics=None):
    if not rows or len(rows) < 24:
        raise AssertionError(
            'Недостатньо даних для перевірки браузера: ' +
            json.dumps({'engine': engine, 'rows': rows, 'diagnostics': diagnostics},
                       ensure_ascii=False, indent=2)
        )
    assert all(row['expected'] == row['actual'] for row in rows), (engine, rows)


def wait_dom_within(page, deadline):
    remaining_ms = (deadline - monotonic()) * 1000
    assert remaining_ms > 0, 'Таймаут навігації до DOMContentLoaded (45 с)'
    page.wait_for_load_state('domcontentloaded', timeout=remaining_ms)


@pytest.mark.parametrize('engine', ('chromium', 'webkit'))
def test_quote_kernel_and_theme_parity_across_browser_engines(pw, server, engine):
    browser = getattr(pw, engine).launch()
    context = browser.new_context(viewport={'width': 390, 'height': 844}, reduced_motion='reduce')
    page = context.new_page()
    errors, console_errors, failures, script_responses = [], [], [], []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda msg: console_errors.append(msg.text) if msg.type == 'error' else None)
    page.on('requestfailed', lambda request: failures.append({'url': request.url, 'failure': request.failure}))
    page.on('response', lambda response: script_responses.append({'url': response.url, 'status': response.status}) if '/js/' in response.url else None)
    try:
        deadline = monotonic() + 45
        response = page.goto(server['base'] + '/', wait_until='networkidle', timeout=45000)
        assert response and response.status == 200
        # WebKit може повернути networkidle до DOMContentLoaded; бюджет залишається 45 с.
        wait_dom_within(page, deadline)
        rows = parity_rows(page)
        diagnostics = None
        if rows is None:
            diagnostics = page.evaluate("""() => ({readyState: document.readyState,
              PBT: typeof window.PBT, quote: typeof window.PBTQuote,
              calc: typeof window.PBTcalc, navigation: performance.getEntriesByType('navigation')[0]?.toJSON()})""")
            diagnostics.update(page_errors=errors, console_errors=console_errors,
                               request_failures=failures, script_responses=script_responses,
                               csp=response.headers.get('content-security-policy'))
        assert_parity_rows(engine, rows, diagnostics)
        page.locator('[data-theme-choice="precision"]').click()
        assert page.evaluate('document.documentElement.dataset.theme') == 'precision'
        deadline = monotonic() + 45
        page.reload(wait_until='networkidle', timeout=45000)
        wait_dom_within(page, deadline)
        assert page.evaluate('document.documentElement.dataset.theme') == 'precision'
        assert not errors, (engine, errors)
    finally:
        context.close()
        browser.close()


@pytest.mark.parametrize('blocked_script', ('data.js', 'site.js'))
def test_parity_rejects_missing_required_script_after_domcontentloaded(pw, server, blocked_script):
    browser = pw.webkit.launch()
    context = browser.new_context(viewport={'width': 390, 'height': 844}, reduced_motion='reduce')
    page = context.new_page()
    failed = []
    page.on('requestfailed', lambda request: failed.append(request.url))
    page.route('**/js/' + blocked_script, lambda route: route.abort())
    try:
        deadline = monotonic() + 45
        response = page.goto(server['base'] + '/', wait_until='networkidle', timeout=45000)
        assert response and response.status == 200
        wait_dom_within(page, deadline)
        rows = parity_rows(page)
        assert rows is None
        with pytest.raises(AssertionError):
            assert_parity_rows('webkit', rows)
        assert any(url.endswith('/js/' + blocked_script) for url in failed)
    finally:
        context.close()
        browser.close()


def test_domcontentloaded_wait_does_not_extend_deadline():
    class NoWait:
        def wait_for_load_state(self, *args, **kwargs):
            pytest.fail('Прострочена навігація не повинна чекати додатково')

    with pytest.raises(AssertionError, match='Таймаут навігації'):
        wait_dom_within(NoWait(), monotonic() - 1)


def test_missing_parity_rows_preserve_full_diagnostics():
    diagnostics = {'padding': 'x' * 5000, 'request_failure': '/js/data.js'}
    with pytest.raises(AssertionError) as failure:
        assert_parity_rows('webkit', None, diagnostics)
    assert json.loads(str(failure.value).split(': ', 1)[1]) == {
        'engine': 'webkit', 'rows': None, 'diagnostics': diagnostics,
    }
