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

if __package__:
    from .support_evidence import Issue, Observation, revise, same
else:
    from support_evidence import Issue, Observation, revise, same

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
REASONS = {
    "mass": "Маса визначає, які конфігурації техніки варто розглядати.",
    "reach": "Допустиме навантаження залежить від вильоту.",
    "access": "Від під’їзду залежить спосіб роботи на об’єкті.",
    "from": "Точка завантаження потрібна для оцінки маршруту.",
    "to": "Пункт призначення потрібен для оцінки маршруту.",
    "depth": "Глибина впливає на підбір техніки.",
}
_TASK_FIRST = re.compile(r"\b(?:підбер\w*|який|котрий)\b.*\b(?:авто)?кран\w*\b", re.I)
_EXPLICIT = re.compile(r"\b(?:виправ\w*|уточнен\w*|підтвердж\w*|точно)\b|^\s*ні[,!]|\bзамість\b|\bтепер\s+(?:до|в|у)\b", re.I)
_TENTATIVE = re.compile(r"\b(?:приблизно|орієнтовно|можливо|мабуть|десь|близько|може|на око|не точно)\b|[≈~]", re.I)
_UNKNOWN = re.compile(r"\b(?:невідом\w*|не зна\w*|не мірял\w*|потрібно уточнити)\b", re.I)
_OPTIONS = re.compile(r"\s*[,;]?\s*(?:(?:а\s+)?може(?:ливо)?|або|чи|до|[-–—])\s*", re.I)
_FIELDS_WITH_UNITS = {"mass", "reach", "length", "width", "depth", "quantity", "area"}
_CONFIRMATION_QUESTION = "Яке значення можете підтвердити?"
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
_CORRECTION = re.compile(r"\bа\s+саме\b|,\s*а\s+(?!(?:потім|далі|також|ще|може|можливо)\b)|\b(?:уточнення|виправ\w*)\s*[:—-]", re.I)
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
_REACH = re.compile(rf"\b(?:виліт|радіус|відстань)\s*[:—-]?\s*(?:(?:приблизно|орієнтовно|десь)\s+)?({_METERS})", re.I)
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
    evidence: dict[str, Observation] = field(default_factory=dict)
    issues: dict[str, Issue] = field(default_factory=dict)
    turn: int = 0
    specialist: bool = False
    focus: str | None = None
    quote_requested: bool = False

    def unresolved(self) -> list[str]:
        required = PRIORITIES.get(self.task, ())
        return [name for name in dict.fromkeys((*required, *self.issues)) if name not in self.values]

    def view(self, handoff: bool, changes: dict[str, str]) -> dict:
        step = plan(self)
        next_step = step.view() if step else None
        issues = [{"label": LABELS[name], "kind": item.kind, "values": [o.value for o in item.options]}
                  for name, item in self.issues.items() if name not in self.skipped]
        issues.extend({"label": LABELS[name], "kind": "unknown", "values": []}
                      for name in LABELS if name in self.skipped)
        return {"stage": "handoff" if handoff else ("clarify" if not self.task or step or self.unresolved() else "ready"),
                "known": self.fields(self.values), "next": next_step if not handoff else None,
                "corrections": self.fields(changes), "issues": issues}

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
        unresolved = self.skipped | self.issues.keys()
        if unresolved:
            comment += ("\n" if comment else "") + "Уточнити: " + ", ".join(
                LABELS[name].lower() for name in LABELS if name in unresolved)
        return {"type": kind, "subject": subject, "place": place, "comment": comment[:1000]}


@dataclass(frozen=True)
class NextStep:
    field: str
    label: str
    question: str
    reason: str = ""

    def view(self) -> dict[str, str]:
        result = {"field": self.field, "label": self.label}
        if self.reason:
            result["reason"] = self.reason
        return result


def plan(brief: Brief) -> NextStep | None:
    """Повертає одне уточнення за правилами задачі й станом свідчень."""
    if not brief.task:
        if brief.proposal:
            return NextStep("confirm_task", "Підтвердити напрям роботи", "")
        return None
    required = PRIORITIES[brief.task]
    order = (*required, *(key for key in brief.issues if key not in required))
    active = [name for name in order if name not in brief.values and name not in brief.skipped]
    if not active:
        return None
    selected = min(active, key=lambda name: (
        0 if name in brief.issues and brief.issues[name].kind == "conflict"
        else 1 if name in brief.issues or name == brief.focus else 2,
        order.index(name),
    ))
    label = LABELS[selected]
    issue = brief.issues.get(selected)
    if not issue:
        return NextStep(selected, label, QUESTIONS[selected], REASONS.get(selected, ""))
    options = " / ".join(entry.value for entry in issue.options)
    reason = ("Є суперечливі дані, які змінюють чернетку." if issue.kind == "conflict"
              else "Попередній параметр потребує підтвердження.")
    preamble = "маю різні дані" if issue.kind == "conflict" else "є попереднє значення"
    question = f"Для параметра «{label.lower()}» {preamble}: {options}. {_CONFIRMATION_QUESTION}"
    return NextStep(selected, label, question, reason)


class BriefMemory:
    """Підписаний короткий стан у вкладці. Без зберігання діалогів на сервері."""

    def __init__(self, clock=time.time):
        self._key = secrets.token_bytes(32)
        self._clock = clock

    def pack(self, brief: Brief) -> str:
        raw = json.dumps([3, int(self._clock()) + _MEMORY_TTL, brief.task, brief.values, sorted(brief.skipped),
                          brief.proposal, {key: item.wire() for key, item in brief.evidence.items()},
                          {key: item.wire() for key, item in brief.issues.items()},
                          brief.turn, brief.specialist, brief.focus, brief.quote_requested],
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
            fields = json.loads(raw)
            if isinstance(fields, list) and len(fields) == 11 and fields[0] == 2:
                fields = [3, *fields[1:], False]
            version, expiry, task, values, skipped, proposal, evidence, issues, turn, specialist, focus, quote = fields
            if version != 3 or expiry <= self._clock() or not isinstance(quote, bool):
                return None
            return Brief(task, values, set(skipped), proposal,
                         {name: Observation(*item) for name, item in evidence.items()},
                         {name: Issue(kind, tuple(Observation(*option) for option in options))
                          for name, (kind, options) in issues.items()}, turn, specialist, focus, quote)
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
    elif pending in {"place", "from", "to"} or task and task != "trans":
        first_phrase = re.split(r"[,.;!?]", text, maxsplit=1)[0].strip()
        if _KNOWN_TOWN.fullmatch(first_phrase):
            values[pending if pending in {"from", "to"} else "place"] = first_phrase[0].upper() + first_phrase[1:]
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


def _alternatives(field, value, text):
    if field not in _FIELDS_WITH_UNITS:
        return [value]
    if field == "mass" or field == "quantity" and _MASS.fullmatch(value):
        # Handles two stated units and the shared-unit shorthand “5 або 8 т”.
        paired = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(?:або|чи|до|[-–—])\s*(" + _MASS.pattern + ")", text, re.I)
        if paired:
            unit = re.sub(r"^[\d.,]+\s*", "", paired[2])
            pair = [f"{paired[1]} {unit}", paired[2]]
            return [pair[0]] if same(field, *pair) else pair
        matches = list(_MASS.finditer(text))
    elif field in {"reach", "length", "width", "depth"}:
        matches = list(re.finditer(_METERS, text, re.I))
    else:
        matches = list((_VOLUME if field == "quantity" else _AREA).finditer(text))
    for left, right in zip(matches, matches[1:]):
        if value not in (left[0], right[0]) or not _OPTIONS.fullmatch(text[left.end():right.start()]):
            continue
        if not same(field, left[0], right[0]):
            return [left[0], right[0]]
    return [value]


def _tentative(value, text):
    for clause in re.split(r"[,;.!?](?!\d)", text):
        if value in clause:
            return bool(_TENTATIVE.search(clause))
    return False


def _unknown_fields(task, text):
    if not task:
        return set()
    labels = {**{name: label.lower().replace("’", "[’'ʼ]") for name, label in LABELS.items()},
              "reach": r"(?:виліт|радіус)", "mass": r"(?:мас[ау]|ваг[ау])"}
    return {name for name in PRIORITIES[task] if re.search(
        rf"\b{labels[name]}\s*[:—-]?\s*(?:{_UNKNOWN.pattern})", text, re.I)}


def advance(brief: Brief, message: str, source="text"):
    """Parse one event, then reconcile each observed value with the working state."""
    text, corrected = _scope(message)
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
    current = Brief(next_task, prior.values.copy(), prior.skipped.copy(), evidence=prior.evidence.copy(),
                    issues=prior.issues.copy(), turn=brief.turn + 1, specialist=prior.specialist,
                    focus="mass" if next_task == "crane" and _TASK_FIRST.search(message) else prior.focus,
                    quote_requested=prior.quote_requested)
    prior_step = plan(prior)
    pending = prior_step.field if prior_step and prior.task else None
    unknown = _unknown_fields(next_task, final)
    if current.task and pending and _SKIP.fullmatch(message.strip()):
        unknown.add(pending)
    for name in unknown:
        current.skipped.add(name)
        current.values.pop(name, None)
        current.evidence.pop(name, None)
        current.issues.pop(name, None)

    evidence = _evidence(next_task, final, pending, corrected)
    if next_task == "exc" and "trans" in topics:
        evidence["secondary"] = "Вивезення ґрунту після земляних робіт"
    explicit = source == "text" and (corrected or _EXPLICIT.search(message))
    edits = {}
    for name, value in evidence.items():
        if name in unknown:
            continue
        observed = tuple(Observation(option, current.turn, source) for option in _alternatives(name, value, final))
        previous = current.evidence.get(name)
        if previous is None and name in current.values:
            previous = Observation(current.values[name], prior.turn)
        direct_answer = (source == "text" and name == pending and name in current.issues
                         and final.strip(" .!").casefold() == value.casefold())
        settled, issue = revise(name, previous, current.issues.get(name), observed,
                                tentative=source != "text" or _tentative(value, final),
                                explicit=bool(explicit or direct_answer))
        current.skipped.discard(name)
        if issue:
            current.issues[name] = issue
            current.values.pop(name, None)
            current.evidence.pop(name, None)
        elif settled:
            if name in current.issues or previous and not same(name, previous.value, settled.value):
                edits[name] = settled.value
            current.issues.pop(name, None)
            current.values[name] = settled.value
            current.evidence[name] = settled
    return current, edits, reset
