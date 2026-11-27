"""Стан об’єкта окремо від реплік. Значення в чернетці походять зі слів клієнта."""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import dataclass, field

MAX_MEMORY = 12_000
_MEMORY_TTL = 2 * 60 * 60

TASKS = {
    "amph": (("водойм", "ставок", "ставк", "мулу", "мулом", "болот", "днопоглиб", "амфіб", "пруд"),
             "rent", "Роботи на водоймі"),
    "crane": (("автокран", "кран", "піднят", "підійм", "поднять", "підйом"),
              "rent", "Підйом вантажу"),
    "trans": (("трал", "самоскид", "негабарит", "перевез", "перевоз", "вивез", "доставити технік"),
              "transport", "Перевезення вантажу"),
    "materials": (("щеб", "пісок", "піск", "відсів", "песок", "матеріал", "граві"),
                  "material", "Постачання матеріалів"),
    "exc": (("транше", "котлован", "екскават", "копат", "розкоп", "рыть"),
            "rent", "Земляні роботи"),
    "bull": (("бульдоз", "корчува", "плануван", "вирівня", "розрівня"),
             "rent", "Підготовка майданчика"),
    "load": (("навантаж", "погрузчик"), "rent", "Навантаження матеріалу"),
    "road": (("грейдер", "асфальт", "ущільн", "каток"), "rent", "Дорожні роботи"),
    "crush": (("дробар", "мульчер", "дроблен", "поросл"), "rent", "Дроблення або розчищення"),
}
LABELS = {
    "place": "Об’єкт", "from": "Звідки", "to": "Куди", "mass": "Маса",
    "reach": "Виліт", "quantity": "Обсяг", "fraction": "Фракція",
    "length": "Довжина", "width": "Ширина", "depth": "Глибина",
    "access": "Під’їзд", "area": "Площа", "when": "Бажаний день", "secondary": "Додаткова робота",
}
QUESTIONS = {
    "place": "Де розташований об’єкт?",
    "from": "Звідки забираємо вантаж?",
    "to": "Куди веземо вантаж?",
    "mass": "Яка маса вантажу?",
    "reach": "Який орієнтовний виліт від місця стоянки крана до точки підйому?",
    "quantity": "Який обсяг або маса потрібні?",
    "fraction": "Яка фракція потрібна, якщо вона відома?",
    "length": "Якої довжини має бути траншея або котлован?",
    "width": "Яка орієнтовна ширина?",
    "depth": "Яка потрібна глибина?",
    "access": "З берега є твердий під’їзд, чи техніка має працювати з води?",
    "area": "Яку приблизно площу треба обробити?",
}

PRIORITIES = {
    "crane": ("place", "mass", "reach"),
    "trans": ("from", "to", "mass"),
    "materials": ("place", "quantity", "fraction"),
    "exc": ("place", "length", "width", "depth"),
    "amph": ("place", "access", "area"),
    "bull": ("place", "area"), "load": ("place", "quantity"),
    "road": ("place", "area"), "crush": ("place", "quantity"),
}
EXPLANATIONS = {
    "crane": "Для підбору крана потрібні маса вантажу, виліт стріли й умови майданчика.",
    "trans": "Для підбору трала спочатку звіримо маршрут і масу вантажу.",
    "exc": "Розміри виїмки впливають на підбір екскаватора й оцінку обсягу роботи.",
    "amph": "Для розчищення водойми спочатку важливо зрозуміти, звідки техніка дістанеться до ділянки.",
    "materials": "Для доставки матеріалу потрібні місце, обсяг і фракція.",
}

_NEW = re.compile(r"\b(?:тепер інше|інша задача|інше завдання|нова задача|нов[аи]й об[’'ʼ]єкт|ще одна заявка)\b", re.I)
_SKIP = re.compile(r"^(?:поки\s+)?(?:не знаю|невідомо|треба уточнити|не мірял\w*|без поняття)[.! ]*$", re.I)
_NEGATED = re.compile(r"\b(?:не потріб\w*|не треб\w*|не хочу|не замов\w*)\b", re.I)
_CORRECTION = re.compile(r"\bа\s+саме\b|,\s*а\s+(?!(?:потім|далі|також|ще)\b)|\b(?:уточнення|виправ\w*)\s*[:—-]", re.I)
_CONFIRM = re.compile(r"^(?:так|саме так|так,?(?: це воно| підходить)|вірно)[.! ]*$", re.I)
_KNOWN_TOWN = re.compile(r"^(?:полтав|кременч|ки[їє]в|харків|черкас|дніпр|житомир|льв[іо]в)\w{0,8}$", re.I)
_NOT_BOX = frozenset(("добре", "дякую", "привіт", "поки", "так", "ні", "зрозуміло", "ок"))
_CITY = r"[А-ЯІЇЄҐ][а-яіїєґ’'ʼ-]+(?:[ -][А-ЯІЇЄҐ][а-яіїєґ’'ʼ-]+){0,2}"
_NAMED_CITY = rf"(?:(?:с\.|м\.|смт|село|місто)\s+)?{_CITY}"
_PLACE = re.compile(rf"(?i:\b(?:місце|об[’'ʼ]єкт|адреса|місто|локація)\s*[:—-]\s*|\b(?:у|в|біля|поряд з|під)\s+)({_NAMED_CITY})")
_FROM = re.compile(rf"(?i:\b(?:забрати\s+)?(?:із|зі|з)\s+)({_NAMED_CITY})")
_TO = re.compile(rf"(?i:\b(?:до|у|в)\s+)({_NAMED_CITY})")
_MASS = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:тонн?\w*|кг|т\b)", re.I)
_METERS = r"\d+(?:[.,]\d+)?\s*(?:м\b|см\b|метр\w*)"
_REACH = re.compile(rf"\b(?:виліт|радіус|відстань)\s*[:—-]?\s*({_METERS})", re.I)
_VOLUME = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:м[³3]|куб\w*)", re.I)
_AREA = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:м[²2]|га\b|сот\w*)", re.I)
_FRACTION = re.compile(r"\b(?:фракці\w*\s*[:—-]?\s*)?(\d{1,3}\s*[-–]\s*\d{1,3})(?=\s*(?:мм\b|[,.!?]|$))", re.I)
_DATE = re.compile(r"\b(?:завтра|післязавтра|на\s+(?:понеділок|вівторок|середу|четвер|п['’]ятницю|суботу|неділю)|\d{4}-\d{2}-\d{2})\b", re.I)
_ACCESS = re.compile(r"(?:нема\w*|є)?\s*(?:тверд\w*\s+)?під[’'ʼ]їзд(?:у)?(?:\s+(?:з|із|зі|до)\s+[а-яіїєґ’'ʼ-]+)?|з берега|з води|берег глинистий|тверда дорога", re.I)
_DIMS = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*(?:на|[×xх])\s*(\d+(?:[.,]\d+)?)(?:\s*(?:на|[×xх])\s*(\d+(?:[.,]\d+)?))?\s*(м\b|см\b)?", re.I)
_NUMBER_WORDS = {
    "один": "1", "одна": "1", "два": "2", "дві": "2", "три": "3", "чотири": "4", "п’ять": "5",
}
_DIM_VALUE = rf"{_METERS}|(?:метр\b|(?:{'|'.join(_NUMBER_WORDS)})\s+метр\w*)"
_DIM_LABELS = {
    "length": r"довжин\w*|завдовжки",
    "width": r"ширин\w*|завширшки",
    "depth": r"глибин\w*|завглибшки",
}


@dataclass
class Brief:
    task: str | None = None
    values: dict[str, str] = field(default_factory=dict)
    skipped: set[str] = field(default_factory=set)
    proposal: str | None = None

    def pending(self) -> str | None:
        if not self.task:
            return None
        return next((name for name in PRIORITIES[self.task] if name not in self.values and name not in self.skipped), None)

    def unresolved(self) -> list[str]:
        return [name for name in PRIORITIES.get(self.task, ()) if name not in self.values]

    def view(self, handoff: bool, changes: dict[str, str]) -> dict:
        pending = self.pending()
        next_step = {"field": pending, "label": LABELS[pending]} if pending else None
        if self.proposal and not self.task:
            next_step = {"field": "confirm_task", "label": "Підтвердити напрям роботи"}
        return {"stage": "handoff" if handoff else ("clarify" if not self.task or pending else "ready"),
                "known": self.fields(self.values), "next": next_step if not handoff else None,
                "corrections": self.fields(changes)}

    @staticmethod
    def fields(values):
        return [{"label": LABELS[name], "value": value} for name, value in values.items()]

    def draft(self):
        if not self.task:
            return None
        _, kind, subject = TASKS[self.task]
        place = self.values.get("place", "")
        if self.task == "trans" and (self.values.get("from") or self.values.get("to")):
            place = " → ".join(filter(None, (self.values.get("from"), self.values.get("to"))))
        comment = "\n".join(f"{LABELS[name]} зі слів клієнта: {value}" for name, value in self.values.items()
                            if name not in {"place", "from", "to"})
        if self.skipped:
            comment += ("\n" if comment else "") + "Уточнити: " + ", ".join(LABELS[name].lower() for name in LABELS if name in self.skipped)
        return {"type": kind, "subject": subject, "place": place, "comment": comment[:1000]}


class BriefMemory:
    """Підписаний короткий стан у вкладці. Без зберігання діалогів на сервері."""

    def __init__(self, clock=time.time):
        self._key = secrets.token_bytes(32)
        self._clock = clock

    def pack(self, brief: Brief) -> str:
        raw = json.dumps([int(self._clock()) + _MEMORY_TTL, brief.task, brief.values, sorted(brief.skipped), brief.proposal],
                         ensure_ascii=False, separators=(",", ":")).encode()
        signature = hmac.digest(self._key, raw, hashlib.sha256)
        return base64.urlsafe_b64encode(signature + raw).decode("ascii")

    def unpack(self, token: str) -> Brief | None:
        if not token or len(token) > MAX_MEMORY:
            return None
        try:
            signed = base64.b64decode(token, altchars=b"-_", validate=True)
            signature, raw = signed[:32], signed[32:]
            if not hmac.compare_digest(signature, hmac.digest(self._key, raw, hashlib.sha256)):
                return None
            expiry, task, values, skipped, proposal = json.loads(raw)
            if expiry <= self._clock():
                return None
            return Brief(task, values, set(skipped), proposal)
        except (ValueError, TypeError, binascii.Error):
            return None


def _topics(message):
    lower = message.casefold()
    found = [name for name, (terms, *_) in TASKS.items() if any(term in lower for term in terms)]
    if "amph" in found and "exc" in found:
        found.remove("exc")
    if "crane" in found and "автокран" in lower:
        found.remove("crane")
        found.insert(0, "crane")
    if "materials" in found and "trans" in found and not re.search("перевез|трал|негабарит", lower):
        found.remove("trans")
    if "exc" in found and "trans" in found and re.search("вивез|самоскид|вивоз", lower):
        return ["exc", "trans"]
    return found


def _scope(message):
    parts = _CORRECTION.split(message)
    scope = next((part for part in reversed(parts) if not _NEGATED.search(part)), "")
    return scope, len(parts) > 1


def _measure(text):
    word, _, _ = text.partition(" ")
    if word.casefold() in _NUMBER_WORDS:
        return _NUMBER_WORDS[word.casefold()] + " м"
    if text.casefold() == "метр":
        return "1 м"
    return text


def _evidence(task, text, pending, corrected):
    values = {}
    if task == "trans":
        start, destination = _FROM.search(text), _TO.search(text)
        if start:
            values["from"] = start[1]
        if destination:
            values["to"] = destination[1]
    elif place := _PLACE.search(text):
        values["place"] = place[1]
    bare_place = re.match(rf"^({_NAMED_CITY})(?=\s*[,.;!?]|$)", text)
    if bare_place and (pending in {"place", "from", "to"} or corrected) and bare_place[1].casefold() not in _NOT_BOX:
        values.setdefault(pending if pending in {"from", "to"} else "place", bare_place[1])
    elif pending in {"place", "from", "to"}:
        first_phrase = re.split(r"[,.;!?]", text, maxsplit=1)[0].strip()
        if _KNOWN_TOWN.fullmatch(first_phrase):
            values[pending] = first_phrase[0].upper() + first_phrase[1:]
    if when := _DATE.search(text):
        values["when"] = when[0]
    if task:
        for name, pattern in (
            ("mass", _MASS), ("area", _AREA), ("access", _ACCESS), ("quantity", _VOLUME),
        ):
            if (hit := pattern.search(text)) and (name in PRIORITIES[task] or task == "exc" and name == "access"):
                values[name] = hit[0].strip()
    if task == "crane":
        if reach := _REACH.search(text):
            values["reach"] = reach[1]
        elif pending == "reach" and re.fullmatch(rf"\s*{_METERS}[.!]?", text, re.I):
            values["reach"] = text.strip(" .!")
    if task == "materials":
        if mass := _MASS.search(text):
            values["quantity"] = mass[0]
        if fraction := _FRACTION.search(text):
            values["fraction"] = fraction[1] + " мм"
    if task == "exc":
        if dimensions := _DIMS.search(text):
            unit = dimensions[4] or "м"
            for label, number in zip(("length", "width", "depth"), dimensions.groups()[:3]):
                if number is not None:
                    values[label] = f"{number} {unit}"
        if "length" not in values and (length := re.search(rf"\b(?:транше\w*|котлован\w*)\s+({_METERS})", text, re.I)):
            values["length"] = length[1]
        for label, words in _DIM_LABELS.items():
            if hit := re.search(rf"\b(?:{words})\s*[:—-]?\s*({_DIM_VALUE})", text, re.I):
                values[label] = _measure(hit[1])
        if pending in _DIM_LABELS and (hit := re.fullmatch(rf"\s*({_DIM_VALUE})[.!]?", text, re.I)):
            values[pending] = _measure(hit[1])
    return values


def advance(brief: Brief, message: str):
    """Take one turn while preserving explicitly separated jobs and replacing only observed fields."""
    text, corrected = _scope(message)
    # Explicit corrections carry facts from the corrected clause, not the rejected clause.
    final = _CORRECTION.split(message)[-1]
    topics = _topics(text)
    explicit_reset = bool(_NEW.search(message))
    additional_transport = (brief.task == "exc" and not explicit_reset and "trans" in topics
                            and re.search(r"\b(?:і|та|ще|потім)\b.*\bвивез", text, re.I))
    if additional_transport and "exc" not in topics:
        topics = ["exc", *topics]
    confirmed = brief.proposal if _CONFIRM.fullmatch(message.strip()) else None
    next_task = topics[0] if topics else (None if explicit_reset else confirmed or brief.task)
    reset = bool(explicit_reset or brief.task and topics and next_task != brief.task)
    prior = Brief() if reset else brief
    current = Brief(next_task, prior.values.copy(), prior.skipped.copy())
    pending = prior.pending()
    if current.task and pending and _SKIP.fullmatch(message.strip()):
        current.skipped.add(pending)
        return current, {}, reset
    evidence = _evidence(next_task, final, pending, corrected)
    if next_task == "exc" and "trans" in topics:
        evidence["secondary"] = "Вивезення ґрунту після земляних робіт"
    edits = {key: value for key, value in evidence.items() if key in current.values and current.values[key] != value}
    current.values.update(evidence)
    current.skipped.difference_update(evidence)
    return current, edits, reset
