"""Валідація підготовки запиту та збереження чернетки заявки."""

import re

import pytest
from playwright.sync_api import expect


def test_material_intake_rejects_blank_and_submits_only_from_the_lead(page_factory):
    page = page_factory(390, 844, mobile=True, reduced=True)
    intake = page.locator("#calcForm")
    kind = intake.locator("#cKind")
    expect(kind).to_be_visible()
    machine = intake.locator("#cMachine")
    if machine.input_value() != "e-1":
        machine.select_option("e-1")
    kind.select_option("material")
    expect(machine).to_be_disabled()
    expect(machine).to_have_value("")
    task = intake.locator("#cTask")
    order = intake.locator("#cOrder")
    subject = page.locator("#subject")
    posted = []
    page.on("request", lambda request: posted.append(request) if request.url.endswith("/api/lead") else None)

    task.fill("   ")
    order.click()
    expect(intake.locator("#cError")).to_contain_text(re.compile(r"\S"))
    expect(subject).to_have_value("")
    assert not posted

    prefix = "Щебінь 5–20 для дороги. "
    boundary_task = prefix + "а" * (160 - len(prefix))
    place = "Решетилівка, склад"
    date = "2099-04-02"
    detail = "12 т, розвантаження зліва"
    task.fill(boundary_task)
    intake.locator("#cPlace").fill(place)
    intake.locator("#cDate").fill(date)
    intake.locator("#cDetail").fill(detail)
    intake.locator("#cFlexible").check()
    page.locator("#comment").fill("Під’їзд через шлагбаум")
    order.click()

    expect(page.locator('#lead input[value="material"]')).to_be_checked()
    expect(subject).to_have_value(boundary_task)
    expect(page.locator("#place")).to_have_value(place)
    expect(page.locator("#date")).to_have_value(date)
    expect(page.locator("#hours")).to_have_value("")
    expect(page.locator("#km")).to_have_value("")
    comment = page.locator("#comment").input_value()
    assert detail in comment and "Дата гнучка" in comment and "Під’їзд через шлагбаум" in comment
    assert "Обрана машина" not in comment
    contact = page.locator("#contact")
    expect(contact).to_be_focused()
    assert not posted

    contact.fill("0675550317")
    with page.expect_response(lambda response: response.url.endswith("/api/lead")) as receipt:
        page.locator("#send").click()
    assert receipt.value.status == 201, receipt.value.text()
    assert len(posted) == 1
    assert posted[0].post_data_json == {
        "type": "material", "subject": boundary_task, "hours": "", "km": "", "place": place, "date": date,
        "name": "", "method": "phone", "contact": "0675550317", "comment": comment, "website": "",
    }


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
