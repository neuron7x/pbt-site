"""Епістемічні інваріанти, що відрізняють спостереження від рішення про чернетку."""
from pathlib import Path

import pytest

from server.support import Support
from server.support_evidence import Observation, same

ROOT = Path(__file__).resolve().parents[1]


class Conversation:
    def __init__(self):
        self.service = Support(ROOT)
        self.token = ""

    def say(self, message, **extra):
        code, response = self.service.reply({"message": message, "memory": self.token, **extra})
        assert code == 200
        self.token = response["memory"]
        return response


@pytest.mark.parametrize(("mass", "kind", "options"), [
    ("приблизно 5 т", "estimate", ["5 т"]),
    ("5 або 8 т", "conflict", ["5 т", "8 т"]),
    ("5–8 т", "conflict", ["5 т", "8 т"]),
    ("можливо 5 т, а може 8 т", "conflict", ["5 т", "8 т"]),
])
def test_estimates_and_alternatives_do_not_become_draft_measurements(mass, kind, options):
    c = Conversation()
    answer = c.say(f"Кран у Полтаві, вантаж {mass}, виліт 12 м")
    assert answer["brief"]["stage"] == "clarify"
    assert answer["brief"]["next"]["field"] == "mass"
    assert answer["brief"]["next"]["reason"]
    assert {"label": "Маса", "kind": kind, "values": options} in answer["brief"]["issues"]
    assert "Маса зі слів клієнта:" not in answer["draft"]["comment"]
    assert any(row == {"label": "Виліт", "value": "12 м"} for row in answer["brief"]["known"])


def test_conflict_preserves_both_sources_across_turns_and_resolves_by_selection():
    c = Conversation()
    assert c.say("Кран у Полтаві, 5 т, виліт 12 м")["brief"]["stage"] == "ready"
    conflict = c.say("За паспортом вантаж 8 т")
    assert conflict["brief"]["issues"] == [{"label": "Маса", "kind": "conflict", "values": ["5 т", "8 т"]}]
    state = c.service._memory.unpack(c.token)
    assert state.issues["mass"].options == (Observation("5 т", 1), Observation("8 т", 2))
    assert c.say("Дякую")["brief"]["stage"] == "clarify"
    resolved = c.say("8 т")
    assert resolved["brief"]["stage"] == "ready" and not resolved["brief"]["issues"]
    assert resolved["brief"]["corrections"] == [{"label": "Маса", "value": "8 т"}]
    assert "8 т" in resolved["draft"]["comment"]


def test_explicit_correction_atomically_supersedes_observation():
    c = Conversation()
    c.say("Кран у Полтаві, 5 т, виліт 12 м")
    corrected = c.say("Виправлення: маса 8 т")
    assert not corrected["brief"]["issues"] and corrected["brief"]["stage"] == "ready"
    assert corrected["brief"]["corrections"] == [{"label": "Маса", "value": "8 т"}]


def test_equivalent_measurements_do_not_create_false_conflict_or_correction():
    assert same("mass", "5 т", "5000 кг")
    assert same("reach", "1200 см", "12 м")
    c = Conversation()
    c.say("Кран у Полтаві, 5 т, виліт 12 м")
    equivalent = c.say("5000 кг, виліт 1200 см")
    assert not equivalent["brief"]["issues"] and not equivalent["brief"]["corrections"]
    assert equivalent["brief"]["stage"] == "ready"


def test_tentative_route_preserves_both_places_and_waits_for_choice():
    c = Conversation()
    c.say("Трал з Полтави до Києва, вантаж 4 т")
    tentative = c.say("Можливо до Львова")
    assert tentative["brief"]["stage"] == "clarify"
    assert tentative["brief"]["next"]["field"] == "to"
    assert tentative["brief"]["issues"] == [{"label": "Куди", "kind": "conflict", "values": ["Києва", "Львова"]}]
    assert tentative["draft"]["place"] == "Полтави"
    assert c.say("Львів")["draft"]["place"] == "Полтави → Львів"


def test_safety_handoff_is_sticky_until_new_task():
    c = Conversation()
    assert c.say("Кран у Полтаві, 5 т, виліт 12 м. Чи безпечно працювати біля ЛЕП?")["handoff"]
    later = c.say("Дякую")
    assert later["handoff"] and later["brief"]["stage"] == "handoff"
    fresh = c.say("Тепер інше: потрібна траншея")
    assert fresh["brief"]["reset"] and not fresh["handoff"]


def test_planner_prioritizes_mass_for_equipment_selection():
    c = Conversation()
    result = c.say("Який автокран підібрати для монтажу?")
    assert result["brief"]["next"]["field"] == "mass"
    assert "конфігурації" in result["brief"]["next"]["reason"]


def test_explicit_unknown_is_not_reasked_and_bare_place_survives():
    c = Conversation()
    result = c.say("Потрібен автокран, маса невідома, виліт 12 м")
    assert result["brief"]["next"]["field"] == "place"
    assert {"label": "Маса", "kind": "unknown", "values": []} in result["brief"]["issues"]
    place = c.say("Полтава")
    assert place["draft"]["place"] == "Полтава"
    assert place["brief"]["stage"] == "handoff" and "Уточнити: маса" in place["draft"]["comment"]


def test_unprocessed_optional_estimate_cannot_leak_as_date_promise():
    c = Conversation()
    c.say("Кран у Полтаві, 5 т, виліт 12 м")
    result = c.say("Можливо на вівторок")
    assert result["brief"]["next"]["field"] == "when"
    assert "вівторок" not in result["draft"]["comment"]


def test_invalid_workspace_token_never_rebuilds_a_safety_state_from_partial_replay():
    c = Conversation()
    c.token = "invalid-signed-state"
    response = c.say("Дякую", history=["Кран у Полтаві, 5 т, виліт 12 м"])
    assert response["brief"]["reset"] and response["draft"] is None
    assert "Попередній контекст більше недоступний" in response["reply"]


def test_direct_answer_can_resolve_a_range_with_an_exact_value_between_the_bounds():
    c = Conversation()
    assert c.say("Кран у Полтаві, 5–8 т, виліт 12 м")["brief"]["next"]["field"] == "mass"
    resolved = c.say("7 т")
    assert resolved["brief"]["stage"] == "ready"
    assert resolved["brief"]["corrections"] == [{"label": "Маса", "value": "7 т"}]
