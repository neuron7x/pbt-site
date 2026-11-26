"""Public navigation paths across catalogue, quote and request."""
import re

from playwright.sync_api import expect


def test_catalogue_passes_the_selected_hourly_machine_into_quote_and_lead(page_factory):
    page = page_factory(reduced=True)
    links = page.locator("#park [data-estimate-machine]")
    assert links.count() > 1
    action = links.nth(1)
    machine = action.get_attribute("data-estimate-machine")
    name = action.locator("xpath=ancestor::article").locator("h3").inner_text()
    assert page.locator("#cMachine").input_value() != machine
    action.click()
    expect(page.locator("#cMachine")).to_have_value(machine)
    expect(page.locator("#cMachine")).to_be_focused()
    page.locator("#cHoursN").fill("8")
    page.locator("#cOrder").click()
    expect(page.locator("#subject")).to_have_value(re.compile(re.escape(name)))
    expect(page.locator("#hours")).to_have_value("8")
    assert page.locator('#park .unit[data-cat="trans"] [data-estimate-machine]').count() == 0


def test_unavailable_passport_reports_error_without_starting_a_request(page_factory):
    page = page_factory(reduced=True)
    page.route("**/js/blueprint.js", lambda route: route.abort())
    card = page.locator("#park .unit").first
    status = card.locator(".unit__status")
    assert status.count() == 1
    passport = card.get_by_role("button", name="Паспорт", exact=False)
    passport.click()
    expect(status).to_contain_text("Паспорт тимчасово недоступний")
    expect(passport).to_be_focused()
    expect(page.locator("#subject")).to_have_value("")
    expect(page.locator("#passport")).to_be_hidden()


def test_mobile_menu_links_and_section_headings_have_readable_names(page_factory):
    page = page_factory(390, 844, mobile=True, reduced=True)
    assert page.locator("#roboty h2").text_content() == "Що саме зробимо"
    page.locator(".burger").click()
    menu = page.locator("#menu nav")
    expect(menu.get_by_role("link", name="Техніка", exact=True)).to_be_visible()
    assert menu.locator("a span").count() == 0
