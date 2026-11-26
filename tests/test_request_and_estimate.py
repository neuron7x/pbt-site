"""Точні значення розрахунку й збереження чернетки заявки."""

import pytest
from playwright.sync_api import expect


def test_exact_estimate_inputs_and_request_handoff(page_factory):
    page = page_factory(390, 844, mobile=True, reduced=True)
    page.select_option("#cMachine", "e-1")
    hours = page.locator("#cHoursN")
    distance = page.locator("#cKmN")
    order = page.locator("#cOrder")

    hours.fill("5000")
    distance.fill("31")
    expect(page.locator("#cOut")).to_have_attribute("data-total", str(5000 * 1350 + 31 * 100))
    distance.fill("3000")
    expect(page.locator("#cOut")).to_have_attribute("data-total", str(5000 * 1350 + 3000 * 100))
    distance.fill("3001")
    expect(order).to_be_disabled()
    expect(page.locator("#cOut")).to_have_attribute("data-total", "")

    page.select_option("#cMachine", "ak-1")
    expect(distance).to_be_disabled()
    expect(order).to_be_enabled()
    expect(order).to_have_attribute("data-calc-km", "")
    page.select_option("#cMachine", "e-1")
    expect(order).to_be_disabled()

    distance.fill("31")
    order.click()
    expect(page.locator("#hours")).to_have_value("5000")
    expect(page.locator("#km")).to_have_value("31")
    assert page.locator("#calcForm").get_by_role("slider").count() == 0


@pytest.mark.parametrize("selector,mobile,open_menu", [
    ('#menu a[href="#zapyt"]', True, True),
    ('#dock a[href="#zapyt"]', True, False),
    ('footer a[href="#zapyt"]', False, False),
])
def test_request_navigation_preserves_draft_and_focuses_subject(page_factory, selector, mobile, open_menu):
    width, height = (390, 844) if mobile else (1440, 900)
    page = page_factory(width, height, mobile=mobile, reduced=True)
    page.locator("#mats .tile").first.get_by_role("button", name="У заявку", exact=True).click()
    subject = page.locator("#subject")
    subject.fill("Щебінь для під’їзду")
    page.locator("#hours").fill("12")
    page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
    if open_menu:
        page.locator(".burger").click()

    page.locator(selector).click()

    expect(page.locator('#lead input[value="material"]')).to_be_checked()
    expect(subject).to_have_value("Щебінь для під’їзду")
    expect(page.locator("#hours")).to_have_value("12")
    expect(subject).to_be_focused()
    assert page.url.endswith("#zapyt")
