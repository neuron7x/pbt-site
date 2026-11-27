"""Перевірка реальних переходів від каталогу й кошторису до заявки."""
from playwright.sync_api import expect
import pytest


def test_no_javascript_cannot_submit_contact_in_url(browser, server):
    ctx = browser.new_context(java_script_enabled=False)
    try:
        page = ctx.new_page()
        page.goto(server['base'], wait_until='domcontentloaded')
        page.locator('#subject').fill('Екскаватор')
        page.locator('#contact').fill('0970000011')
        page.locator('#contact').press('Enter')
        page.wait_for_timeout(300)
        assert '0970000011' not in page.url
        expect(page.locator('#send')).to_be_disabled()
        assert page.locator('a[href="tel:+380675550317"]').count() > 0
        expect(page.locator('#cOrder')).to_be_disabled()
        expect(page.locator('#cMachine')).to_be_disabled()
        expect(page.locator('#cOut')).to_contain_text('Вартість договірна')
        page.locator('#cTask').fill('Тестове завдання')
        page.locator('#cTask').press('Enter')
        assert '?' not in page.url
        expect(page.locator('#park .content-fallback')).to_be_visible()
        expect(page.locator('#mats .content-fallback')).to_be_visible()
        expect(page.locator('#calcUnavailable')).to_be_visible()
        expect(page.locator('#formUnavailable')).to_be_visible()
    finally:
        ctx.close()


def test_broken_site_script_keeps_submit_disabled(browser, server):
    ctx = browser.new_context()
    try:
        page = ctx.new_page()
        page.route('**/js/site.js', lambda route: route.abort())
        page.goto(server['base'], wait_until='domcontentloaded')
        expect(page.locator('#send')).to_be_disabled()
        assert not page.locator('html').evaluate("e => e.classList.contains('reveal-ready')")
        assert page.locator('#roboty .sec-head').evaluate("e => getComputedStyle(e).opacity") == '1'
        expect(page.locator('#park .content-fallback')).to_be_visible()
        expect(page.locator('#mats .content-fallback')).to_be_visible()
        expect(page.locator('#channels a[href="tel:+380675550317"]')).to_have_count(1)
        expect(page.locator('#calcUnavailable')).to_be_visible()
        expect(page.locator('#formUnavailable')).to_be_visible()
    finally:
        ctx.close()


def test_transport_cards_choose_transport_request(page_factory):
    page = page_factory(reduced=True)
    expect(page.locator('#park .content-fallback')).to_have_count(0)
    expect(page.locator('#mats .content-fallback')).to_have_count(0)
    expect(page.locator('#calcUnavailable')).to_be_hidden()
    expect(page.locator('#formUnavailable')).to_be_hidden()
    for card in page.locator('#park .unit[data-cat="trans"]').all():
        name = card.locator('h3').text_content()
        card.locator('[data-req]').click()
        expect(page.locator('input[name="type"][value="transport"]')).to_be_checked()
        expect(page.locator('#subject')).to_have_value(name)
    page.locator('#park .unit[data-cat="exc"] [data-req]').first.click()
    expect(page.locator('input[name="type"][value="rent"]')).to_be_checked()


def test_brief_carries_job_context_and_preserves_customer_details(page_factory):
    page = page_factory(reduced=True)
    expect(page.locator('#cOrder')).to_have_text('Перейти до заявки')
    page.locator('#name').fill('Олена')
    page.locator('#hours').fill('99')
    page.locator('#km').fill('999')
    page.locator('#comment').fill('Заїзд із провулка')
    page.locator('#cTask').fill('Викопати траншею')
    page.locator('#cPlace').fill('Полтава')
    page.locator('#cDate').fill('2099-06-15')
    page.locator('#cDetail').fill('60 м траншеї')
    page.locator('#cMachine').select_option('ak-1')
    page.locator('#cFlexible').check()
    page.locator('#cTask').press('Enter')
    expect(page.locator('#contact')).to_be_focused()
    expect(page.locator('#subject')).to_have_value('Викопати траншею')
    expect(page.locator('#place')).to_have_value('Полтава')
    expect(page.locator('#date')).to_have_value('2099-06-15')
    expect(page.locator('#name')).to_have_value('Олена')
    expect(page.locator('#hours')).to_have_value('99')
    expect(page.locator('#km')).to_have_value('999')
    comment = page.locator('#comment').input_value()
    assert '60 м траншеї' in comment
    assert 'Обрана машина' in comment
    assert 'Дата гнучка' in comment
    assert 'Заїзд із провулка' in comment
    page.locator('#cOrder').click()
    expect(page.locator('#comment')).to_have_value(comment)


def test_brief_fields_do_not_leak_into_other_request_types(page_factory):
    page = page_factory(reduced=True)
    assert page.locator('#cTask').count() == 1
    page.locator('#place').fill('Стара адреса')
    page.locator('#date').fill('2099-06-01')
    page.locator('#comment').fill('Мій коментар')
    page.locator('#cTask').fill('Викопати траншею')
    page.locator('#cPlace').fill('Нова адреса')
    page.locator('#cDate').fill('2099-06-15')
    page.locator('#cDetail').fill('60 м траншеї')
    page.locator('#cOrder').click()
    expect(page.locator('#place')).to_have_value('Нова адреса')
    expect(page.locator('#date')).to_have_value('2099-06-15')
    page.locator('#mats .tile:first-child [data-req]').click()
    expect(page.locator('#place')).to_have_value('Стара адреса')
    expect(page.locator('#date')).to_have_value('2099-06-01')
    expect(page.locator('#comment')).to_have_value('Мій коментар')
    page.locator('#cOrder').click()
    page.locator('#place').fill('Адреса з ручного вводу')
    page.locator('#comment').fill('Коментар з ручного вводу')
    page.locator('#mats .tile:first-child [data-req]').click()
    expect(page.locator('#place')).to_have_value('Адреса з ручного вводу')
    expect(page.locator('#comment')).to_have_value('Коментар з ручного вводу')


def test_manual_quantities_follow_their_request_type(page_factory):
    page = page_factory(reduced=True)
    assert page.locator('#cTask').count() == 1
    page.locator('#hours').fill('99')
    page.locator('#km').fill('33')
    page.locator('#cTask').fill('Викопати траншею')
    page.locator('#cOrder').click()
    page.locator('#mats .tile:first-child [data-req]').click()
    expect(page.locator('#hours')).to_have_value('')
    expect(page.locator('#km')).to_have_value('33')
    page.locator('#hours').fill('24')
    page.locator('#park .unit[data-cat="exc"] [data-req]').first.click()
    expect(page.locator('#hours')).to_have_value('99')
    expect(page.locator('#km')).to_have_value('33')
    page.locator('#mats .tile:first-child [data-req]').click()
    expect(page.locator('#hours')).to_have_value('24')
    page.locator('#lead input[name="type"][value="transport"]').check(force=True)
    expect(page.locator('#hours')).to_have_value('')
    page.locator('#hours').fill('7')
    page.locator('#lead input[name="type"][value="material"]').check(force=True)
    expect(page.locator('#hours')).to_have_value('24')
    expect(page.locator('#km')).to_have_value('33')


@pytest.mark.parametrize('mobile', [False, True])
def test_generic_request_restores_subject_for_its_own_type(page_factory, mobile):
    page = page_factory(390 if mobile else 1440, 844 if mobile else 900,
                        mobile=mobile, reduced=True)
    page.locator('#subject').fill('Ручне завдання оренди')
    page.locator('#name').fill('Олена')
    material = page.locator('#mats .tile:first-child')
    selected = material.locator('h3').text_content()
    material.locator('[data-req]').click()
    expect(page.locator('#subject')).to_have_value(selected)
    page.evaluate('window.scrollTo({top:0,behavior:"instant"})')
    page.wait_for_function('() => scrollY === 0 && !document.querySelector("#nav").classList.contains("is-hidden")')
    if mobile:
        page.locator('#heroCenter [data-req="rent"]').click()
    else:
        page.locator('.nav__cta[data-req="rent"]').click()
    expect(page.locator('input[name="type"][value="rent"]')).to_be_checked()
    expect(page.locator('#subject')).to_have_value('Ручне завдання оренди')
    expect(page.locator('#name')).to_have_value('Олена')
    # Ручне перемикання також не переносить тему між видами заявки.
    page.locator('#lead input[name="type"][value="material"]').check(force=True)
    expect(page.locator('#subject')).to_have_value(selected)
    page.locator('#lead input[name="type"][value="transport"]').check(force=True)
    expect(page.locator('#subject')).to_have_value('')
    page.locator('#subject').fill('Маршрут Полтава — Київ')
    page.locator('#lead input[name="type"][value="rent"]').check(force=True)
    expect(page.locator('#subject')).to_have_value('Ручне завдання оренди')
    page.locator('#lead input[name="type"][value="transport"]').check(force=True)
    expect(page.locator('#subject')).to_have_value('Маршрут Полтава — Київ')


def test_first_generic_request_clears_subject_from_other_type(page_factory):
    page = page_factory(reduced=True)
    page.locator('#mats .tile:first-child [data-req]').click()
    page.evaluate('window.scrollTo({top:0,behavior:"instant"})')
    page.wait_for_function('() => scrollY === 0 && !document.querySelector("#nav").classList.contains("is-hidden")')
    page.locator('.nav__cta[data-req="rent"]').click()
    expect(page.locator('input[name="type"][value="rent"]')).to_be_checked()
    expect(page.locator('#subject')).to_have_value('')


def test_generic_request_does_not_leave_a_stale_brief_subject(page_factory):
    page = page_factory(reduced=True)
    assert page.locator('#cTask').count() == 1
    page.locator('#subject').fill('Ручне завдання')
    page.locator('#hours').fill('7')
    page.locator('#km').fill('8')
    page.locator('#cTask').fill('Викопати траншею')
    page.locator('#cOrder').click()
    expect(page.locator('#subject')).to_have_value('Викопати траншею')
    page.evaluate('window.scrollTo({top:0,behavior:"instant"})')
    page.wait_for_function('() => scrollY === 0 && !document.querySelector("#nav").classList.contains("is-hidden")')
    page.locator('.nav__cta[data-req="rent"]').click()
    expect(page.locator('#subject')).to_have_value('Ручне завдання')
    expect(page.locator('#hours')).to_have_value('7')
    expect(page.locator('#km')).to_have_value('8')


def test_brief_refuses_comment_overflow_without_editing_the_draft(page_factory):
    page = page_factory(reduced=True)
    assert page.locator('#cTask').count() == 1
    page.locator('#subject').fill('Моя чернетка')
    personal = 'A' * 990
    page.locator('#comment').fill(personal)
    page.locator('#cTask').fill('Викопати траншею')
    page.locator('#cDetail').fill('60 метрів, обмежений під’їзд')
    page.locator('#cOrder').click()
    expect(page.locator('#cError')).to_be_visible()
    expect(page.locator('#subject')).to_have_value('Моя чернетка')
    expect(page.locator('#comment')).to_have_value(personal)
    page.locator('#comment').fill('A' * 100)
    page.locator('#cOrder').click()
    expect(page.locator('#cError')).to_be_hidden()
    expect(page.locator('#subject')).to_have_value('Викопати траншею')
    assert len(page.locator('#comment').input_value()) <= 1000


def test_telegram_contact_has_usable_mobile_keyboard(page_factory):
    page = page_factory(390, 844, mobile=True, reduced=True)
    page.locator('#method').select_option('telegram')
    expect(page.locator('#contact')).to_have_attribute('inputmode', 'text')
    expect(page.locator('#contact')).to_have_attribute('placeholder', '@username або номер телефону')
    page.locator('#method').select_option('phone')
    expect(page.locator('#contact')).to_have_attribute('inputmode', 'tel')


def test_brief_mobile_exposes_selected_full_machine_name(page_factory):
    page = page_factory(390, 844, mobile=True, reduced=True)
    assert page.locator('#cTask').count() == 1
    page.locator('#cMachine').select_option('e-2')
    text = page.locator('#cMachine option:checked').inner_text()
    expect(page.locator('#cMachineSummary')).to_have_text(text)
    expect(page.locator('#cMachineSummary')).to_be_visible()
    assert page.locator('#cMachineSummary').get_attribute('aria-hidden') == 'true'


def test_known_contacts_show_before_config_request_finishes(browser, server):
    ctx = browser.new_context(reduced_motion='reduce')
    try:
        ctx.add_init_script("""(() => {
          const original = window.fetch;
          window.fetch = (...args) => {
            if (String(args[0]).includes('/api/config')) {
              window.__configPending = true;
              return new Promise(() => {});
            }
            return original(...args);
          };
        })();""")
        page = ctx.new_page()
        page.goto(server['base'], wait_until='domcontentloaded')
        page.wait_for_function('() => window.PBT && document.querySelectorAll("#park .unit").length > 0')
        assert page.evaluate('window.__configPending === true')
        expect(page.locator('#channels a[href="tel:+380675550317"]')).to_have_count(1)
        expect(page.locator('#cOrder')).to_have_text('Перейти до заявки')
    finally:
        ctx.close()


def test_initial_deep_link_and_reload_reach_section(page_factory):
    page = page_factory(390, 844, mobile=True, path='/#cina')
    page.wait_for_function("""() => { const r = document.querySelector('#cina').getBoundingClientRect();
       return r.top >= 0 && r.top < innerHeight / 2; }""", timeout=5000)
    page.reload(wait_until='networkidle')
    page.wait_for_function("""() => { const r = document.querySelector('#cina').getBoundingClientRect();
       return r.top >= 0 && r.top < innerHeight / 2; }""", timeout=5000)


def test_completed_brief_reuses_identity_with_a_fresh_job(page_factory):
    page = page_factory(reduced=True)
    assert page.locator("#cTask").count() == 1
    page.locator("#cTask").fill("Підготувати котлован")
    page.locator("#cPlace").fill("Полтава")
    page.locator("#cDetail").fill("Старі деталі")
    page.locator("#cOrder").click()
    page.locator("#name").fill("Олена")
    page.locator("#contact").fill("097 000 00 11")
    page.locator("#send").click()
    expect(page.locator("#done")).to_have_class("done is-on")

    page.locator("#cKind").select_option("material")
    page.locator("#cTask").fill("Щебінь для під’їзду")
    page.locator("#cPlace").fill("")
    page.locator("#cDetail").fill("")
    page.locator("#cOrder").click()
    expect(page.locator("#lead input[value='material']")).to_be_checked()
    expect(page.locator("#subject")).to_have_value("Щебінь для під’їзду")
    expect(page.locator("#place")).to_have_value("")
    expect(page.locator("#comment")).to_have_value("")
    expect(page.locator("#name")).to_have_value("Олена")
    expect(page.locator("#contact")).to_have_value("097 000 00 11")
