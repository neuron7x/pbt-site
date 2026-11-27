"""Інтерфейс допомоги проходить до чинної форми без надсилання заявки."""
import pytest


@pytest.mark.parametrize("viewport", [(1440, 900, False), (390, 844, True)])
def test_support_workspace_transfers_an_editable_draft_without_sending(page_factory, viewport):
    width, height, mobile = viewport
    page = page_factory(width, height, mobile=mobile, reduced=True)
    launcher = page.locator("[data-support-open]").first
    assert launcher.count() == 1
    assert page.locator("#supportKnown").count() == 1
    lead_requests = []
    page.on("request", lambda request: lead_requests.append(request.url) if request.url.endswith("/api/lead") else None)
    launcher.click()
    message = page.locator("#supportMessage")
    message.fill("Хочу очистити водойму у Полтаві")
    page.locator("#supportSend").click()
    if mobile:
        page.get_by_role("button", name="Переглянути чернетку").click()
    draft = page.locator("#supportDraft")
    draft.wait_for(state="visible")
    assert "під’їзд" in page.locator("#supportTimeline").inner_text()
    assert not page.locator("#supportAttachments").is_visible()
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
    assert page.locator("#supportKnown").count() == 1
    launcher.click()
    for index, message in enumerate((
        "Потрібен автокран у Полтаві, вантаж 5 т. Вантаж потрібно зняти з платформи, перенести через проїзд та поставити на майданчик.",
        "Не Полтава, а Кременчук. Виліт 8 м. На об’єкті вже є відповідальна людина, яка покаже місце встановлення.",
    ), 1):
        page.locator("#supportMessage").fill(message)
        page.locator("#supportSend").click()
        page.locator(".support__message--agent").nth(index).wait_for(state="visible")
    assert page.locator(".support__conversation").evaluate("(node) => node.scrollTop") > 0
    assert page.locator(".support__workspace").evaluate("(node) => node.scrollTop") == 0
    assert page.locator("#supportDraftPlace").input_value() == "Кременчук"


def test_brief_uses_latest_facts_and_keeps_only_the_manually_edited_field(page_factory):
    page = page_factory(390, 844, mobile=True, reduced=True)
    launcher = page.locator("[data-support-open]").first
    assert launcher.count() == 1
    assert page.locator("#supportBriefView").count() == 1
    assert page.locator("#supportKnown").count() == 1
    requests = []
    first = {"type": "rent", "subject": "Монтаж", "place": "Полтава", "comment": "Маса 4 т"}
    corrected = {"type": "rent", "subject": "Монтаж техніки", "place": "Кременчук", "comment": "Маса 5 т"}
    responses = iter([
        {"reply": "Який виліт?", "draft": first, "memory": "opaque-state-one", "brief": {
            "stage": "clarify", "known": [{"label": "Об’єкт", "value": "Полтава"}],
            "next": {"field": "reach", "label": "Виліт"},
        }},
        {"reply": "Зміни внесено.", "draft": corrected, "memory": "opaque-state-two", "brief": {
            "stage": "ready", "known": [{"label": "Об’єкт", "value": "Кременчук"}], "next": None,
            "corrections": [{"label": "Об’єкт", "value": "Кременчук"}],
        }},
        {"reply": "Починаємо заново."},
    ])

    def respond(route):
        if route.request.method == "GET":
            route.fulfill(json={"available": True, "mode": "local", "attachments": False})
        else:
            requests.append(route.request.post_data_json)
            route.fulfill(json={"ok": True, "mode": "local", **next(responses)})

    page.route("**/api/support", respond)
    launcher.click()
    page.locator("#supportMessage").fill("Монтаж у Полтаві, 4 т")
    page.locator("#supportSend").click()
    page.get_by_role("button", name="Переглянути чернетку").click()
    assert page.get_by_role("button", name="Завдання", exact=True).get_attribute("aria-pressed") == "true"
    assert "Полтава" in page.locator("#supportKnown").inner_text()
    assert "Виліт" in page.locator("#supportNext").inner_text()
    page.locator("#supportDraftSubject").fill("Мій опис монтажу")
    page.get_by_role("button", name="Розмова", exact=True).click()
    page.locator("#supportMessage").fill("Кременчук, 5 т, виліт 10 м")
    page.locator("#supportSend").click()
    page.get_by_text("Зміни внесено.").wait_for(state="visible")
    page.get_by_role("button", name="Завдання", exact=True).click()
    assert "Кременчук" in page.locator("#supportKnown").inner_text()
    assert "Оновлено" in page.locator("#supportKnown").inner_text()
    assert page.locator("#supportStage").inner_text() == "Можна звірити чернетку · за вашим описом"
    assert not page.locator("#supportNext").is_visible()
    assert not page.locator("#supportMessage").is_visible()
    assert page.locator("#supportDraftSubject").input_value() == "Мій опис монтажу"
    assert page.locator("#supportDraftPlace").input_value() == "Кременчук"
    assert page.locator("#supportDraftComment").input_value() == "Маса 5 т"
    assert requests[1]["memory"] == "opaque-state-one"
    page.get_by_role("button", name="Розмова", exact=True).click()
    page.locator("#supportClear").click()
    assert not page.locator("#supportKnown").is_visible()
    page.locator("#supportMessage").fill("Нова задача")
    page.locator("#supportSend").click()
    page.get_by_text("Починаємо заново.").wait_for(state="visible")
    assert "memory" not in requests[0] and "memory" not in requests[2]
    assert requests[2]["history"] == []


def test_support_preserves_an_unprocessed_attachment_for_explicit_retry(page_factory):
    page = page_factory(1440, 900, reduced=True)
    launcher = page.locator("[data-support-open]").first
    assert launcher.count() == 1
    requests = []

    def respond(route):
        if route.request.method == "GET":
            route.fulfill(json={"available": True, "mode": "model", "provider": "OpenAI", "attachments": True})
        else:
            requests.append(route.request.post_data_json)
            processed = len(requests) == 2
            route.fulfill(json={"ok": True, "mode": "model", "reply": "Отримано." if processed else "Спробуйте ще раз.",
                               "media": {"status": "used" if processed else "unprocessed"}})

    page.route("**/api/support", respond)
    launcher.click()
    page.locator("#supportAttachments").wait_for(state="visible")
    attachment = page.locator("#supportFile")
    attachment.set_input_files({"name": "place.png", "mimeType": "image/png", "buffer": b"synthetic"})
    page.locator("#supportConsent").check()
    page.locator("#supportSend").click()
    page.get_by_text("Спробуйте ще раз.").wait_for(state="visible")
    assert "Вкладення не опрацьовано." in page.locator("#supportStatus").inner_text()
    assert attachment.evaluate("(element) => element.files.length") == 1
    assert not page.locator("#supportConsent").is_checked()
    page.locator("#supportConsent").check()
    page.locator("#supportSend").click()
    page.get_by_text("Отримано.").wait_for(state="visible")
    assert attachment.evaluate("(element) => element.files.length") == 0
    assert requests[0]["attachment"] == requests[1]["attachment"]
    assert all(request["consent"] for request in requests)


@pytest.mark.parametrize("edited", [False, True])
def test_new_task_cannot_transfer_previous_draft(page_factory, edited):
    page = page_factory(1440, 900, reduced=True)
    launcher = page.locator("[data-support-open]").first
    assert launcher.count() == 1
    assert page.locator("#supportDraftTitle").count() == 1
    assert page.locator("#supportNewDraft").count() == 1
    previous = {"type": "rent", "subject": "Траншея", "place": "Полтава", "comment": "Глибина 2 м"}
    current = {"type": "rent", "subject": "Підйом", "place": "Кременчук", "comment": "Маса 4 т"}
    replies = iter([
        {"reply": "Параметри першої роботи.", "draft": previous},
        {"reply": "Перейшли до іншої роботи.", "draft": current if edited else None, "brief": {"reset": True}},
    ])

    def respond(route):
        if route.request.method == "GET":
            route.fulfill(json={"available": True, "mode": "local", "attachments": False})
        else:
            route.fulfill(json={"ok": True, "mode": "local", **next(replies)})

    page.route("**/api/support", respond)
    launcher.click()
    page.locator("#supportMessage").fill("Траншея в Полтаві")
    page.locator("#supportSend").click()
    page.locator("#supportDraft").wait_for(state="visible")
    if edited:
        page.locator("#supportDraftComment").fill("Моя правка для траншеї")
    page.locator("#supportMessage").fill("Інше завдання, потрібен кран")
    page.locator("#supportSend").click()
    page.get_by_text("Перейшли до іншої роботи.").wait_for(state="visible")
    if not edited:
        assert not page.locator("#supportDraft").is_visible()
        assert page.locator("#supportDraftComment").input_value() == ""
    else:
        assert page.locator("#supportDraftTitle").text_content() == "Попередня чернетка"
        assert page.locator("#supportDraftComment").input_value() == "Моя правка для траншеї"
        assert page.locator("#supportApply").is_disabled()
        page.locator("#supportNewDraft").click()
        assert page.locator("#supportDraftSubject").input_value() == "Підйом"
        assert page.locator("#supportDraftComment").input_value() == "Маса 4 т"
        assert page.locator("#supportApply").is_enabled()
    assert page.locator("#subject").input_value() == ""


@pytest.mark.parametrize("viewport", [(1440, 900, False), (390, 844, True)])
def test_brief_keeps_uncertainty_separate_and_explains_next_question(page_factory, viewport):
    width, height, mobile = viewport
    page = page_factory(width, height, mobile=mobile, reduced=True)
    issues = page.locator("#supportIssues")
    assert issues.count() == 1
    responses = iter([
        {"reply": "Яку масу брати для підбору?", "brief": {
            "stage": "clarify",
            "known": [{"label": "Маса", "value": "5 т"}, {"label": "Місто", "value": "Полтава"}],
            "issues": [
                {"label": "Маса", "kind": "conflict", "values": ["5 т", "8 т"]},
                {"label": "Виліт", "kind": "estimate", "values": ["12 м"]},
                {"label": "Під’їзд", "kind": "unknown", "values": []},
            ],
            "next": {"field": "mass", "label": "Маса", "reason": "Від маси залежить підбір крана."},
        }},
        {"reply": "Записав, 8 т.", "brief": {
            "stage": "ready",
            "known": [{"label": "Маса", "value": "8 т"}],
        }},
    ])

    def respond(route):
        if route.request.method == "GET":
            route.fulfill(json={"available": True, "mode": "local", "attachments": False})
        else:
            route.fulfill(json={"ok": True, "mode": "local", **next(responses)})

    page.route("**/api/support", respond)
    page.locator("[data-support-open]").first.click()
    page.locator("#supportMessage").fill("Потрібен кран")
    page.locator("#supportSend").click()
    page.get_by_text("Яку масу брати для підбору?").wait_for(state="visible")
    if mobile:
        page.get_by_role("button", name="Завдання", exact=True).click()
    assert "Полтава" in page.locator("#supportKnown").inner_text()
    assert "Маса" not in page.locator("#supportKnown").inner_text()
    assert "Суперечливі дані · 5 т / 8 т" in issues.inner_text()
    assert "Орієнтовно · 12 м" in issues.inner_text()
    assert "Невідомо" in issues.inner_text()
    assert "Від маси залежить підбір крана." in page.locator("#supportNext").inner_text()
    if mobile:
        page.get_by_role("button", name="Розмова", exact=True).click()
    page.locator("#supportMessage").fill("Точно 8 т")
    page.locator("#supportSend").click()
    page.get_by_text("Записав, 8 т.").wait_for(state="visible")
    if mobile:
        page.get_by_role("button", name="Завдання", exact=True).click()
    assert "8 т" in page.locator("#supportKnown").inner_text()
    assert not issues.is_visible() and not page.locator("#supportNext").is_visible()


def test_visible_audio_transcript_is_not_replayed_as_typed_history(page_factory):
    page = page_factory(1440, 900, reduced=True)
    launcher = page.locator("[data-support-open]").first
    assert launcher.count() == 1
    posts = []

    def respond(route):
        if route.request.method == "GET":
            route.fulfill(json={"available": True, "mode": "model", "provider": "OpenAI", "attachments": True})
            return
        posts.append(route.request.post_data_json)
        response = {"ok": True, "mode": "model", "reply": "Звіряємо параметри."}
        if len(posts) == 1:
            response.update(reply="Дані отримано.", transcript="У записі може бути 12 м.",
                            memory="separate-signed-evidence")
        route.fulfill(json=response)

    page.route("**/api/support", respond)
    launcher.click()
    page.locator("#supportMessage").fill("Додаю аудіо")
    page.locator("#supportFile").set_input_files(
        {"name": "recording.wav", "mimeType": "audio/wav", "buffer": b"synthetic"}
    )
    page.locator("#supportConsent").check()
    page.locator("#supportSend").click()
    page.get_by_text("У записі може бути 12 м.").wait_for(state="visible")
    page.locator("#supportMessage").fill("Чи бракує даних?")
    page.locator("#supportSend").click()
    page.get_by_text("Звіряємо параметри.", exact=True).wait_for(state="visible")
    assert len(posts) == 2
    assert posts[1]["message"] == "Чи бракує даних?"
    assert posts[1]["history"] == ["Додаю аудіо"]
    assert posts[1]["memory"] == "separate-signed-evidence"
