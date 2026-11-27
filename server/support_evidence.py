"""Оновлення свідчень клієнта. Парсинг і вибір запитання лишаються зовні."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Observation:
    value: str
    turn: int
    source: str = "text"

    def wire(self):
        return [self.value, self.turn, self.source]


@dataclass(frozen=True)
class Issue:
    kind: str
    options: tuple[Observation, ...]

    def wire(self):
        return [self.kind, [entry.wire() for entry in self.options]]


_MEASUREMENT = re.compile(r"(\d{1,18}(?:[.,]\d{1,8})?)\s*(кг|тонн?\w*|т|см|метр\w*|м)", re.I)
_DISTANCE = {"reach", "length", "width", "depth"}
_PLACE_FIELDS = {"place", "from", "to"}
_INFLECTIONS = tuple(re.compile(pattern, re.I) for pattern in (
    r"полтав[аиію]", r"кременчу(?:к|ка|ку|ці)", r"ки(?:їв|єва|єві|єву)",
    r"льв(?:ів|ова|ові|ову)", r"харків|харко(?:ва|ві|ву)", r"черкас(?:и|ах|ам)?",
))


def _unit_value(field, value):
    if field not in _DISTANCE | {"mass", "quantity"}:
        return None
    hit = _MEASUREMENT.fullmatch(value.strip())
    if not hit:
        return None
    amount = Decimal(hit[1].replace(",", "."))
    unit = hit[2].lower()
    if unit.startswith("т") or unit == "кг":
        return "kg", amount if unit == "кг" else amount * 1000
    return "m", amount / 100 if unit == "см" else amount


def same(field, left, right):
    if " ".join(left.lower().split()) == " ".join(right.lower().split()):
        return True
    if field in _PLACE_FIELDS and any(rule.fullmatch(left.strip()) and rule.fullmatch(right.strip())
                                      for rule in _INFLECTIONS):
        return True
    unit_left = _unit_value(field, left)
    return bool(unit_left is not None and unit_left == _unit_value(field, right))


def revise(field, previous, issue, incoming, *, tentative=False, explicit=False):
    """Один перехід без бізнес-дій. Різні свідчення потребують вибору клієнта."""
    first = incoming[0]
    if len(incoming) == 1:
        if not tentative and explicit:
            return first, None
        if previous and same(field, previous.value, first.value):
            return previous, None
        if issue and not tentative and any(same(field, option.value, first.value) for option in issue.options):
            return first, None
        if not tentative and previous is None and issue is None:
            return first, None

    options = list(issue.options) if issue else ([previous] if previous else [])
    for observed in incoming:
        if not any(same(field, item.value, observed.value) for item in options):
            options.append(observed)
    # Three alternatives are enough to describe a blocked field. Keep the first
    # account and the two most recent distinct alternatives.
    if len(options) > 3:
        options = [options[0], *options[-2:]]
    return None, Issue("conflict" if len(options) > 1 else "estimate", tuple(options))
