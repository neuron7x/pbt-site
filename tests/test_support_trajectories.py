"""Оракули багатокрокового розбору. Перевіряємо стан і рішення на кожній репліці."""
import base64
from pathlib import Path

import pytest

from server.support import Support
from server.support_intake import Brief, BriefMemory

ROOT = Path(__file__).resolve().parents[1]


class Dialogue:
    def __init__(self, provider=None):
        self.service = Support(ROOT, provider)
        self.memory = ""

    def say(self, message, **extra):
        code, answer = self.service.reply({"message": message, "memory": self.memory, **extra})
        assert code == 200 and answer["ok"] is True
        self.memory = answer["memory"]
        return answer


def brief(data):
    return {row["label"]: row["value"] for row in data["brief"]["known"]}


def next_field(data):
    item = data["brief"]["next"]
    return item["field"] if item else None


def test_crane_uses_pending_slot_for_short_reply_and_remembers_working_state():
    d = Dialogue()
    assert next_field(d.say("Потрібен автокран")) == "place"
    asked = d.say("Кременчук, 5 т")
    assert brief(asked) == {"Об’єкт": "Кременчук", "Маса": "5 т"}
    assert next_field(asked) == "reach"
    answered = d.say("12 м")
    assert next_field(answered) is None and answered["brief"]["stage"] == "ready"
    assert brief(answered)["Виліт"] == "12 м" and "?" not in answered["reply"]
    # No transcript/history is submitted. The task survives every turn after the old replay limit.
    for _ in range(8):
        retained = d.say("Добре")
        assert brief(retained) == brief(answered)
    wish = d.say("На вівторок")
    assert brief(wish)["Бажаний день"] == "На вівторок"
    assert "На вівторок" in wish["draft"]["comment"]
    assert d.say("Можна живого оператора?")["handoff"] is True


def test_new_job_cannot_inherit_old_mass_location_or_date():
    d = Dialogue()
    old = d.say("Треба перевезти 4 т з Полтави до Києва на вівторок")
    assert brief(old)["Маса"] == "4 т" and old["draft"]["type"] == "transport"
    fresh = d.say("Тепер інше: потрібен автокран для монтажу")
    assert brief(fresh) == {} and fresh["draft"]["place"] == ""
    assert fresh["draft"]["subject"] == "Підйом вантажу" and next_field(fresh) == "place"
    assert "4 т" not in fresh["draft"]["comment"] and "окрему" in fresh["reply"]


def test_route_update_does_not_replace_origin_or_unrelated_fields():
    d = Dialogue()
    assert next_field(d.say("Трал з Полтави до Києва")) == "mass"
    assert next_field(d.say("Вантаж 4 т")) is None
    changed = d.say("Ні, тепер до Львова")
    assert changed["draft"]["place"] == "Полтави → Львова"
    assert changed["brief"]["corrections"] == [{"label": "Куди", "value": "Львова"}]
    assert brief(changed)["Маса"] == "4 т"


def test_material_quantity_in_tonnes_and_correction_remain_typed():
    d = Dialogue()
    result = d.say("Пісок, треба 25 т у Полтаві")
    assert next_field(result) == "fraction" and brief(result)["Обсяг"] == "25 т"
    changed = d.say("Не 25, а 20 т")
    assert brief(changed)["Обсяг"] == "20 т"
    assert "25 т" not in changed["draft"]["comment"]
    assert d.say("0–5 мм")["brief"]["stage"] == "ready"


@pytest.mark.parametrize("turns", [
    ["Треба траншея 100 м, ширина 40 см, на глибину метр, у Полтаві, а потім вивезти ґрунт самоскидом"],
    ["Треба траншея 100 м, ширина 40 см, на глибину метр, у Полтаві", "І вивезти ґрунт самоскидом"],
])
def test_excavation_and_haul_preserve_scope_and_independent_dimensions(turns):
    d = Dialogue()
    for message in turns:
        result = d.say(message)
    values = brief(result)
    assert result["draft"]["subject"] == "Земляні роботи"
    assert (values["Довжина"], values["Ширина"], values["Глибина"]) == ("100 м", "40 см", "1 м")
    assert values["Додаткова робота"] == "Вивезення ґрунту після земляних робіт"


def test_unknown_measurement_moves_on_and_records_dispatcher_question():
    d = Dialogue()
    assert next_field(d.say("Кран у Полтаві")) == "mass"
    skipped = d.say("Поки не знаю")
    assert next_field(skipped) == "reach" and "Маса" not in brief(skipped)
    handoff = d.say("8 м")
    assert handoff["brief"]["stage"] == "handoff"
    assert "Уточнити: маса" in handoff["draft"]["comment"]


def test_signed_memory_cannot_be_modified_and_expires():
    now = [1700000000]
    service = BriefMemory(lambda: now[0])
    token = service.pack(Brief("crane", {"mass": "5 т"}))
    assert service.unpack(token).values == {"mass": "5 т"}
    assert service.unpack(("A" if token[0] != "A" else "B") + token[1:]) is None
    now[0] += 7200
    assert service.unpack(token) is None


def test_model_prose_cannot_create_dispatch_or_safety_guarantee():
    class Provider:
        def answer(self, *args):
            return {"reply": "Автокран X-600 вже призначено на суботу, він точно підніме цей вантаж.",
                    "fact_ids": ["crane"]}, None

    result = Dialogue(Provider()).say("Кран у Полтаві, 5 т", consent=True)
    assert result["mode"] == "model" and next_field(result) == "reach"
    assert "X-600" not in result["reply"] and "точно підніме" not in result["reply"]
    assert "Бажаний день" not in brief(result)


def test_model_suggestion_opens_a_job_only_on_user_confirmation():
    class Provider:
        def answer(self, *args):
            return {"reply": "Можливі земляні роботи.", "fact_ids": ["exc"]}, None

    d = Dialogue(Provider())
    suggestion = d.say("Треба підготувати місце під фундамент", consent=True)
    assert suggestion["draft"] is None and next_field(suggestion) == "confirm_task"
    confirmed = d.say("Так")
    assert confirmed["draft"]["subject"] == "Земляні роботи" and next_field(confirmed) == "place"


def test_dispatch_can_be_requested_without_a_job():
    result = Dialogue().say("Як із вами зв’язатися?")
    assert result["handoff"] and result["brief"]["stage"] == "handoff"
    assert result["sources"] == [{"label": "Заявка диспетчеру", "href": "#zapyt"}]


def test_media_is_reported_as_unprocessed_when_the_turn_is_dispatch_only():
    class Provider:
        def answer(self, *args):
            pytest.fail("price request must not send the attachment")

    png = base64.b64encode(b"\x89PNG\r\n\x1a\n0000").decode()
    result = Dialogue(Provider()).say("Скільки коштує ця траншея?", consent=True,
                                     attachment={"mime": "image/png", "data": png})
    assert result["handoff"] and result["media"] == {"status": "unprocessed"}
    assert "Файл не опрацьовано" in result["reply"]
