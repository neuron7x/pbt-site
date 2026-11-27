"""Інтерфейс допомоги проходить до чинної форми без надсилання заявки."""
import pytest


@pytest.mark.parametrize("viewport", [(1440, 900, False), (390, 844, True)])
def test_support_workspace_transfers_an_editable_draft_without_sending(page_factory, viewport):
    width, height, mobile = viewport
    page = page_factory(width, height, mobile=mobile, reduced=True)
    launcher = page.locator("[data-support-open]").first
    assert launcher.count() == 1
    lead_requests = []
    page.on("request", lambda request: lead_requests.append(request.url) if request.url.endswith("/api/lead") else None)
    launcher.click()
    message = page.locator("#supportMessage")
    message.fill("Хочу очистити водойму у Полтаві")
    page.locator("#supportSend").click()
    draft = page.locator("#supportDraft")
    draft.wait_for(state="visible")
    assert "під’їзд" in page.locator("#supportTimeline").inner_text()
    assert not page.locator("#supportAttachments").is_visible()
    if mobile:
        page.get_by_role("button", name="Переглянути чернетку").click()
    page.locator("#supportDraftPlace").fill("Полтава")
    page.locator("#supportApply").click()
    assert not page.locator("#supportPanel").is_visible()
    assert page.locator("#subject").input_value() == "Роботи на водоймі"
    assert page.locator("#place").input_value() == "Полтава"
    assert not lead_requests


def test_support_does_not_close_when_all_lead_fields_are_already_filled(page_factory):
    page = page_factory(1440, 900, reduced=True)
    launcher = page.locator("[data-support-open]").first
    assert launcher.count() == 1
    page.locator("#subject").fill("Моя техніка")
    page.locator("#place").fill("Моя адреса")
    page.locator("#comment").fill("Мої деталі")
    launcher.click()
    page.locator("#supportMessage").fill("Потрібен автокран у Полтаві, вантаж 5 т")
    page.locator("#supportSend").click()
    page.locator("#supportApply").click()
    assert page.locator("#supportPanel").is_visible()
    assert "Наявні поля збережено" in page.locator("#supportStatus").inner_text()
    assert page.locator("#subject").input_value() == "Моя техніка"


def test_long_desktop_conversation_scrolls_independently_of_draft(page_factory):
    page = page_factory(1440, 900, reduced=True)
    launcher = page.locator("[data-support-open]").first
    assert launcher.count() == 1
    launcher.click()
    for message, expected in (
        ("Потрібен автокран у Полтаві, вантаж 5 т", "Який орієнтовний виліт"),
        ("Не Полтава, а Кременчук. Виліт 8 м.", "У чернетці вже є тип роботи й місце"),
    ):
        page.locator("#supportMessage").fill(message)
        page.locator("#supportSend").click()
        page.get_by_text(expected, exact=False).wait_for(state="visible")
    assert page.locator(".support__conversation").evaluate("(node) => node.scrollTop") > 0
    assert page.locator(".support__workspace").evaluate("(node) => node.scrollTop") == 0
    assert page.locator("#supportDraftPlace").input_value() == "Кременчук"
