"""Маршрути від каталогу до підготовки й чернетки заявки."""
import re

import pytest

from playwright.sync_api import expect


@pytest.mark.parametrize(("unit_id", "kind", "task"), [
    ("e-1", "rent", "Розробити котлован"),
    ("tr-2", "transport", "Перевезти екскаватор"),
])
def test_catalogue_passes_the_selected_machine_into_intake_and_lead(page_factory, unit_id, kind, task):
    page = page_factory(reduced=True)
    card = page.locator(f'#park .unit[data-id="{unit_id}"]')
    action = card.locator("[data-estimate-machine]")
    expect(action).to_be_visible()
    name = card.locator("h3").inner_text()
    expect(card.locator(".unit__price")).to_have_text(re.compile(r"^договірна$", re.IGNORECASE))
    posted = []
    page.on("request", lambda request: posted.append(request) if request.url.endswith("/api/lead") else None)

    action.click()
    expect(page.locator("#cKind")).to_have_value(kind)
    expect(page.locator("#cMachine")).to_have_value(unit_id)
    expect(page.locator("#cTask")).to_be_focused()
    expect(page.locator("#subject")).to_have_value("")
    page.locator("#cTask").fill(task)
    page.locator("#cOrder").click()

    expect(page.locator(f'#lead input[value="{kind}"]')).to_be_checked()
    expect(page.locator("#subject")).to_have_value(task)
    expect(page.locator("#comment")).to_have_value(re.compile(rf"Обрана машина:\s*{re.escape(name)}"))
    expect(page.locator("#contact")).to_be_focused()
    assert not posted, "Підготовка чернетки не надсилає заявку"


def test_mobile_menu_links_and_section_headings_have_readable_names(page_factory):
    page = page_factory(390, 844, mobile=True, reduced=True)
    assert page.locator("#roboty h2").text_content() == "Що саме зробимо"
    page.locator(".burger").click()
    menu = page.locator("#menu nav")
    expect(menu.get_by_role("link", name="Техніка", exact=True)).to_be_visible()
    assert menu.locator("a span").count() == 0
