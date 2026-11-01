"""DB-05 / INV-02: commit the lead, lose the response, reload, resubmit the same request."""
import json
import sqlite3

from playwright.sync_api import expect


def _fill(page, contact='0971112233', subject='Екскаватор для тесту повтору'):
    page.locator('#subject').fill(subject)
    page.locator('#contact').fill(contact)


def _lose_response_once(page):
    """The server commits; the browser never hears about it."""
    state = {'lost': 0}

    def handler(route):
        if state['lost'] == 0 and route.request.method == 'POST':
            state['lost'] = 1
            state['key'] = route.request.headers.get('idempotency-key')
            route.fetch()
            route.abort('connectionreset')
        else:
            route.continue_()
    page.route('**/api/lead', handler)
    return state


def _count(db, subject):
    with sqlite3.connect(db) as c:
        return sum(json.loads(p)['subject'] == subject for (p,) in c.execute('SELECT payload FROM leads'))


def _open(page_factory):
    return page_factory(reduced=True, path='/#zapyt')


def test_lost_response_then_reload_replays_the_same_lead(page_factory, server):
    subject = 'Повтор після перезавантаження A'
    page = _open(page_factory)
    state = _lose_response_once(page)
    _fill(page, subject=subject)
    page.locator('#send').click()
    expect(page.locator('#fallback')).to_be_visible()
    assert _count(server['db'], subject) == 1
    page.reload(wait_until='networkidle')
    page.wait_for_timeout(300)
    seen = []
    page.on('request', lambda r: seen.append(r.headers.get('idempotency-key')) if r.method == 'POST' else None)
    _fill(page, subject=subject)
    with page.expect_response('**/api/lead') as info:
        page.locator('#send').click()
    body = info.value.json()
    assert info.value.status == 201 and body.get('replayed') is True
    assert seen == [state['key']]
    assert _count(server['db'], subject) == 1
    expect(page.locator('#done')).to_be_visible()


def test_storage_holds_no_contact_data_and_clears_on_confirmation(page_factory, server):
    subject = 'Повтор: приватність сховища'
    contact = '0977654321'
    page = _open(page_factory)
    _lose_response_once(page)
    _fill(page, contact=contact, subject=subject)
    page.locator('#send').click()
    expect(page.locator('#fallback')).to_be_visible()
    stored = page.evaluate('() => JSON.stringify({s: {...sessionStorage}, l: {...localStorage}})')
    assert contact not in stored and subject not in stored and contact[1:] not in stored
    assert 'pbt.pendingLead' in stored
    record = json.loads(page.evaluate("() => sessionStorage.getItem('pbt.pendingLead')"))
    assert set(record) == {'k', 'd', 'x'}
    page.unroute('**/api/lead')
    page.locator('#fbRetry').click()
    with page.expect_response('**/api/lead') as info:
        page.locator('#send').click()
    assert info.value.status == 201
    expect(page.locator('#done')).to_be_visible()
    assert page.evaluate("() => sessionStorage.getItem('pbt.pendingLead')") is None


def test_changed_payload_after_reload_is_a_new_intent_not_a_conflict(page_factory, server):
    subject = 'Повтор: новий намір'
    page = _open(page_factory)
    _lose_response_once(page)
    _fill(page, subject=subject)
    page.locator('#send').click()
    expect(page.locator('#fallback')).to_be_visible()
    page.reload(wait_until='networkidle')
    page.wait_for_timeout(300)
    _fill(page, subject=subject + ' змінено')
    with page.expect_response('**/api/lead') as info:
        page.locator('#send').click()
    assert info.value.status == 201 and 'replayed' not in info.value.json()
    assert _count(server['db'], subject) == 1 and _count(server['db'], subject + ' змінено') == 1


def test_expired_record_is_not_reused(page_factory, server):
    subject = 'Повтор: прострочений запис'
    page = _open(page_factory)
    _lose_response_once(page)
    _fill(page, subject=subject)
    page.locator('#send').click()
    expect(page.locator('#fallback')).to_be_visible()
    page.evaluate("""() => { const r = JSON.parse(sessionStorage.getItem('pbt.pendingLead'));
                     r.x = Date.now() - 1; sessionStorage.setItem('pbt.pendingLead', JSON.stringify(r)); }""")
    page.reload(wait_until='networkidle')
    page.wait_for_timeout(300)
    _fill(page, subject=subject)
    with page.expect_response('**/api/lead') as info:
        page.locator('#send').click()
    assert info.value.status == 201 and 'replayed' not in info.value.json()
    assert _count(server['db'], subject) == 2  # Documented boundary: TTL expiry means a new intent.


def test_blocked_storage_degrades_to_in_memory_idempotency(browser, server):
    ctx = browser.new_context(reduced_motion='reduce')
    ctx.add_init_script("""Object.defineProperty(window, 'sessionStorage',
        { get() { throw new DOMException('blocked', 'SecurityError'); } });""")
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        page.goto(server['base'] + '/#zapyt', wait_until='networkidle')
        page.wait_for_timeout(300)
        subject = 'Повтор: сховище заблоковане'
        _lose_response_once(page)
        _fill(page, subject=subject)
        page.locator('#send').click()
        expect(page.locator('#fallback')).to_be_visible()
        page.unroute('**/api/lead')
        page.locator('#fbRetry').click()
        with page.expect_response('**/api/lead') as info:
            page.locator('#send').click()
        assert info.value.status == 201 and info.value.json().get('replayed') is True
        assert _count(server['db'], subject) == 1 and errors == []
    finally:
        ctx.close()
