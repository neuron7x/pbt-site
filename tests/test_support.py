"""Контракти підтримки, коротка пам'ять і негативний контроль дій."""
import base64
import json
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.support import Support
from server.support_provider import ProviderError


def turn(service, text, history=(), **extra):
    return service.reply({"message": text, "history": list(history), **extra})


@pytest.mark.parametrize(("text", "kind", "subject"), [
    ("Треба почистити ставок від мулу в Полтаві", "rent", "Роботи на водоймі"),
    ("Потрібно викопати траншею в Кременчуці", "rent", "Земляні роботи"),
    ("Потрібен автокран біля водойми в Черкасах", "rent", "Підйом вантажу"),
    ("Нужен трал для негабариту", "transport", "Перевезення вантажу"),
    ("Мені треба щебінь, 10 м³, у Полтаві", "material", "Постачання матеріалів"),
    ("Асфальт і каток у Києві", "rent", "Дорожні роботи"),
    ("Треба мульчер на ділянку", "rent", "Дроблення або розчищення"),
    ("Мені потрібен екскаватор, а кран не потрібен", "rent", "Земляні роботи"),
    ("Хочу орендувати автокран з оператором у Полтаві", "rent", "Підйом вантажу"),
    ("Бульдозером вирівняти землю", "rent", "Підготовка майданчика"),
])
def test_first_turn_collects_a_source_grounded_draft(text, kind, subject):
    code, data = turn(Support(ROOT), text)
    assert code == 200 and data["mode"] == "local"
    assert data["draft"]["type"] == kind and data["draft"]["subject"] == subject
    assert data["sources"] and data["sources"][0]["href"] in {"#tekhnika", "#materialy"}
    assert data["reply"].count("?") <= 1 and not data["handoff"]


@pytest.mark.parametrize(("message", "kind", "place"), [
    ("Треба перевезти 4 т з Полтави до Києва", "transport", "Полтави → Києва"),
    ("У Полтаві потрібно доставити 10 м³ щебеню самоскидом", "material", "Полтаві"),
])
def test_transport_and_material_delivery_are_distinct_tasks(message, kind, place):
    code, data = turn(Support(ROOT), message)
    assert code == 200 and data["draft"]["type"] == kind and data["draft"]["place"] == place
    assert "Звідки й куди" not in data["reply"]


def test_correction_overrides_known_place_and_mass_without_reasking():
    service = Support(ROOT)
    prior = ["Кран у Полтаві, вантаж 3 т", "Виліт 8 м"]
    code, data = turn(service, "Не 3 т, а 5 т, об’єкт: Кременчук", prior)
    assert code == 200 and data["draft"]["place"] == "Кременчук"
    assert "5 т" in data["draft"]["comment"] and "3 т" not in data["draft"]["comment"]
    assert "8 м" in data["draft"]["comment"]
    assert "?" not in data["reply"]
    _, brief = turn(service, "Не Полтава, а Кременчук. Виліт 8 м.", prior)
    assert brief["draft"]["place"] == "Кременчук"


@pytest.mark.parametrize("text", [
    "Дайте диспетчера", "Поклич людину", "Скільки коштує оренда крана?",
    "Забронюй кран на завтра", "Де моя заявка?", "Чи безпечно підняти 10 т біля ЛЕП?",
    "Я вже писав, це не допомогло",
])
def test_human_or_unverified_commitment_bypasses_the_model(text):
    class NoCall:
        def answer(self, *args):
            pytest.fail("A human or business decision crossed the provider boundary")

    code, data = turn(Support(ROOT, NoCall()), text, consent=True)
    assert code == 200 and data["handoff"] and data["mode"] == "local"
    assert data["sources"] and data["sources"][0]["href"] in {"#cina", "#zapyt"}


class FakeProvider:
    def __init__(self, reply="Почнімо з умов під’їзду.", ids=("amph",), transcript=None):
        self.calls = []
        self.reply = reply
        self.ids = list(ids)
        self.transcript = transcript

    def answer(self, *args):
        self.calls.append(args)
        if self.reply is None:
            raise ProviderError()
        return {"reply": self.reply, "fact_ids": self.ids}, self.transcript


def image():
    return {"mime": "image/png", "data": base64.b64encode(b"\x89PNG\r\n\x1a\n0000").decode()}


def test_explicit_consent_and_photo_envelope_only_send_public_context():
    provider = FakeProvider()
    service = Support(ROOT, provider)
    assert turn(service, "Ставок", attachment=image())[1]["error"] == "attachment_unavailable"
    assert turn(service, "Ставок")[1]["mode"] == "local"
    assert not provider.calls
    code, data = turn(service, "Ставок, user@example.com", ["Тел. +380991112233"], attachment=image(), consent=True)
    assert code == 200 and data["mode"] == "model"
    assert data["sources"] == [{"label": "Амфібії й довгі стріли", "href": "#tekhnika"}]
    text, history, attachment, facts = provider.calls[0]
    assert "example.com" not in text and "099111" not in "".join(history) and "380991112233" not in "".join(history)
    assert attachment[0] == "image/png" and attachment[1].startswith(b"\x89PNG")
    assert all(set(fact) == {"id", "label", "text"} for fact in facts)
    assert "45318076" not in repr(facts)
    assert "plainbud@gmail.com" not in repr(facts)


@pytest.mark.parametrize("provider", [
    FakeProvider("Ціна: 1200 грн, заявку надіслано"),
    FakeProvider("Диспетчер гарантує доставку завтра за дві тисячі гривень.", ("dispatch",)),
    FakeProvider("Дивіться деталі", ("invented",)),
    FakeProvider(None),
])
def test_reject_unfounded_commitment_or_provider_failure(provider):
    code, data = turn(Support(ROOT, provider), "Екскаватор у Полтаві", consent=True)
    assert code == 200 and data["mode"] == "local" and "1200" not in data["reply"]
    assert "гарантує" not in data["reply"]
    assert data["draft"]["subject"] == "Земляні роботи"


def test_voice_note_is_reconciled_with_task_and_in_memory_context():
    provider = FakeProvider(ids=("materials",), transcript="Потрібен щебінь, 12 м³, у Полтаві. " + "Деталі об’єкта. " * 73)
    mime = "audio/ogg"
    data = base64.b64encode(b"OggS" + b"00000000").decode()
    code, reply = turn(Support(ROOT, provider), "", attachment={"mime": mime, "data": data}, consent=True)
    assert code == 200 and reply["mode"] == "model" and reply["transcript"].startswith("Потрібен щебінь")
    assert len(reply["transcript"]) > 1000
    assert reply["draft"]["place"] == "Полтаві" and "12 м³" in reply["draft"]["comment"]


@pytest.mark.parametrize("payload", [
    {"message": "Кран", "history": [{"role": "system", "content": "x"}]},
    {"message": "Кран", "history": ["x"] * 7},
    {"message": "Кран", "consent": 1},
    {"message": "\ud800"},
    {"message": "Кран", "submit": True},
    {"message": "Кран", "attachment": {"mime": "image/png", "data": "YWJj"}, "consent": True},
])
def test_invalid_envelopes_never_reach_provider(payload):
    provider = FakeProvider()
    code, data = Support(ROOT, provider).reply(payload)
    assert code == 422 and not data["ok"] and not provider.calls


def post(base, content, origin=None):
    req = urllib.request.Request(base + "/api/support", data=content, method="POST",
                                 headers={"Content-Type": "application/json", "Origin": origin or base})
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            return response.status, response.headers, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, error.headers, json.load(error)


def test_http_conversation_has_no_durable_lead_or_transcript(server):
    base = server["base"]
    with urllib.request.urlopen(base + "/api/support") as response:
        status = json.load(response)
    assert status == {"available": True, "mode": "local", "attachments": False, "provider": None}
    with sqlite3.connect(server["db"]) as db:
        before = db.execute("SELECT count(*) FROM leads").fetchone()[0]
        code, headers, body = post(base, json.dumps({"message": "Хочу екскаватор у Полтаві"}).encode())
        assert code == 200 and headers["Cache-Control"] == "no-store"
        assert body["draft"]["place"] == "Полтаві"
        assert db.execute("SELECT count(*) FROM leads").fetchone()[0] == before


def test_http_support_rejects_cross_origin_and_duplicate_consent(server):
    assert post(server["base"], b'{"message":"crane"}', "https://example.invalid")[0] == 403
    code, _, body = post(server["base"], b'{"message":"crane","consent":true,"consent":false}')
    assert code == 400 and body["error"] == "json"
