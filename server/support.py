"""Розбір задачі ПЛЕЙНБУД. Публічні факти, коротка пам'ять і чернетка без запису заявки."""
from __future__ import annotations

import base64
import binascii
import json
import re
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

if __package__:
    from .support_provider import CONTACT_PATTERN, TRANSCRIPT_MAX, ProviderError, redact_contacts
else:
    from support_provider import CONTACT_PATTERN, TRANSCRIPT_MAX, ProviderError, redact_contacts

MAX_BODY = 2_140_000
IMAGE_MAX = 1024 * 1024
AUDIO_MAX = 3 * 1024 * 1024 // 2
HISTORY_MAX = 6
MESSAGE_MAX = 1000


class InputError(ValueError):
    pass


class Provider(Protocol):
    def answer(self, message: str, history: list[str], attachment: tuple[str, bytes] | None,
               facts: list[dict[str, str]]) -> tuple[dict, str | None]: ...


@dataclass(frozen=True)
class Fact:
    id: str
    label: str
    href: str
    text: str

    def for_provider(self):
        return {"id": self.id, "label": self.label, "text": self.text}


POLICY = {
    "price": Fact("price", "Договірна ціна", "#cina",
                  "Кошторис готує диспетчер після уточнення об'єкта й обсягу робіт."),
    "dispatch": Fact("dispatch", "Умови виїзду", "#zapyt",
                     "Наявність техніки, виїзд і строки підтверджує диспетчер після розгляду задачі."),
    "request": Fact("request", "Заявка диспетчеру", "#zapyt",
                    "Після заповнення чернетку можна переглянути й надіслати через форму заявки."),
    "materials": Fact("materials", "Матеріали", "#materialy",
                      "Для матеріалів важливі вид, фракція, обсяг і місце доставки."),
}

# Порівняння з основами слів витримує відмінки та поширені розмовні формулювання.
TASKS = {
    "amph": (("водойм", "ставок", "ставк", "мулу", "мулом", "болот", "днопоглиб", "амфіб", "пруд"),
             "rent", "Роботи на водоймі", "З берега є твердий під’їзд, чи техніка має працювати з води?"),
    "crane": (("автокран", "кран", "піднят", "підійм", "поднять", "підйом", "погруз"),
              "rent", "Підйом вантажу", "Яка маса вантажу й відстань від місця стоянки крана до точки підйому?"),
    "trans": (("трал", "самоскид", "негабарит", "перевез", "перевоз", "доставити технік"),
              "transport", "Перевезення вантажу", "Звідки й куди везти вантаж?"),
    "materials": (("щеб", "пісок", "піск", "відсів", "песок", "матеріал", "граві"),
                  "material", "Постачання матеріалів", "Який обсяг потрібен і яка фракція, якщо вона вже відома?"),
    "exc": (("транше", "котлован", "екскават", "копат", "розкоп", "траншею", "рыть"),
            "rent", "Земляні роботи", "Які приблизні розміри котловану чи траншеї?"),
    "bull": (("бульдоз", "корчува", "плануван", "вирівня", "розрівня"),
             "rent", "Підготовка майданчика", "Яка приблизна площа роботи?"),
    "load": (("навантаж", "погрузчик"), "rent", "Навантаження матеріалу", "Який матеріал і обсяг потрібно перемістити?"),
    "road": (("грейдер", "асфальт", "ущільн", "каток"), "rent", "Дорожні роботи", "Яке покриття та яку площу потрібно підготувати?"),
    "crush": (("дробар", "мульчер", "дроблен", "поросл"), "rent", "Дроблення або розчищення", "Який матеріал і обсяг роботи?"),
}

HUMAN = re.compile(r"\b(?:диспетчер\w*|менеджер\w*|людин\w*|человек\w*)\b", re.I)
HUMAN_INTENT = re.compile(r"\b(?:поклич|дайте|дай|з'єднай|з’єднай|підключ|хочу|можна|поговор|зв'яз|зв’яз|зв'яж|зв’яж|контакт|телефон|номер)\w*\b", re.I)
OPERATOR_HANDOFF = re.compile(r"\b(?:поклич|з'єднай|з’єднай|підключ|дайте|дай)\w*\s+(?:мені\s+)?оператора\b", re.I)
PRICE = re.compile(r"\bцін(?:а|и|у|ою|і|ах|ам)\b|скільки кошту|сколько сто|прайс|тариф|вартіст|кошторис|\bгрн\b", re.I)
BOOKING = re.compile(r"брон\w*|наявн\w*|вільн\w*|свобод\w*|\b(?:буде|є)\s+.{0,20}\b(?:завтра|сьогодні)\b|(?:статус|де\s+моя|що\s+з\s+моєю)\s+заяв", re.I)
DANGER = re.compile(r"безпек|безпечн|вантажопідйом|можна підняти|чи підніме|выдержит|строп|електроліні|леп\b|обвал|аварі|травм", re.I)
COVERAGE = re.compile(r"географ|виїжджає|виїжджа|обслуговуєте|працюєте.{0,20}\b(?:у|в|по)\b|област\w*.*працю", re.I)
CORRECTION = re.compile(r"(?:\bа\s+саме\b|,\s*а\s+|\bуточнення\s*[:—-]|\bвиправ\w*\s*[:—-])", re.I)
_CITY = r"[А-ЯІЇЄҐ][а-яіїєґ’'ʼ-]+(?:[ -][А-ЯІЇЄҐ][а-яіїєґ’'ʼ-]+){0,2}"
LOCATION = re.compile(rf"(?i:\b(?:місце|об[’'ʼ]єкт|адреса|місто|локація)\s*[:—-]\s*|\b(?:у|в|біля|поряд з|під)\s+)({_CITY})")
ROUTE = re.compile(rf"(?i:\b(?:з|із|зі)\s+)({_CITY})(?i:\s+(?:до|в|у)\s+)({_CITY})")
NEGATED_TASK = re.compile(r"\b(?:не потріб\w*|не треб\w*|не хочу|не замов\w*)\b", re.I)
EXPLICIT_TRANSPORT = re.compile(r"перевез|перевоз|трал|негабарит", re.I)

QUANTITY = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:тонн?\w*|кг|т\b|метр\w*|м(?:²|³|2|3)?\b|куб\w*|га\b)", re.I)
ACCESS = re.compile(r"під['’ʼ]їзд|з берега|з води|тверд\w* доро|\bз\s+[^,.]+\s+(?:до|в)\s+", re.I)
DETAILS = re.compile(r"\b\d+\s*(?:мм|см|x|×)|фракці|глибин|ширин|висот|довжин|площ", re.I)
MASS = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:тонн?\w*|кг|т\b)", re.I)
REACH = re.compile(r"\b(?:виліт|радіус|відстань)\s*[:—-]?\s*\d+(?:[.,]\d+)?\s*(?:метр\w*|м\b)", re.I)
VOLUME = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:м[³3]|куб\w*)", re.I)
REPEAT = re.compile(r"повторю(?:юсь|юся)|вже (?:писав|казав)|не допомог|не те|знову пита", re.I)
CLOUD_COMMITMENT = re.compile(
    r"\d[\d\s.,]*(?:\s+тисяч\w*)?\s*(?:грн|грив|uah|₴|долар|євро)|[₴$€]\s*\d|(?:ціна|вартість)\s*[:—]\s*\d|"
    r"гривн|гаранту\w*|\b(?:заброньовано|забронювали|підтверджено|заявку (?:надіслано|прийнято)|"
    r"техніка (?:є в наявності|буде|виїде|вільна)|статус заявки\s*[:—])\b", re.I)



def _media_matches(mime: str, raw: bytes) -> bool:
    if mime == "image/jpeg":
        return raw.startswith(b"\xff\xd8\xff") and raw.endswith(b"\xff\xd9")
    if mime == "image/png":
        return raw.startswith(b"\x89PNG\r\n\x1a\n")
    if mime == "image/webp":
        return raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"
    if mime == "audio/wav":
        return raw.startswith(b"RIFF") and raw[8:12] == b"WAVE"
    if mime == "audio/mpeg":
        return raw.startswith(b"ID3") or raw[0] == 0xff and raw[1] & 0xe0 == 0xe0
    if mime == "audio/webm":
        return raw.startswith(b"\x1a\x45\xdf\xa3")
    if mime == "audio/mp4":
        return raw[4:8] == b"ftyp"
    return mime == "audio/ogg" and raw.startswith(b"OggS")


def _text(value, limit):
    if not isinstance(value, str) or len(value) > limit or any(
            (ord(c) < 32 and c not in "\t\n\r") or 0xd800 <= ord(c) <= 0xdfff for c in value):
        raise InputError("validation")
    return value.strip()


def _attachment(value, consent, provider):
    if value is None:
        return None
    if not consent or provider is None:
        raise InputError("attachment_unavailable")
    if not isinstance(value, dict) or value.keys() != {"mime", "data"}:
        raise InputError("attachment")
    mime, encoded = value["mime"], value["data"]
    if not isinstance(mime, str) or not isinstance(encoded, str):
        raise InputError("attachment")
    limit = IMAGE_MAX if mime.startswith("image/") else AUDIO_MAX
    if len(encoded) > ((limit + 2) // 3) * 4:
        raise InputError("attachment")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise InputError("attachment") from error
    if not 12 <= len(raw) <= limit or not _media_matches(mime, raw):
        raise InputError("attachment")
    return mime, raw


def _facts(root: Path) -> dict[str, Fact]:
    facts = dict(POLICY)
    catalog = json.loads((root / "data" / "catalog.json").read_text(encoding="utf-8"))
    config = json.loads((root / "config" / "business.json").read_text(encoding="utf-8"))
    for category in catalog["cats"]:
        key = category["id"]
        if key in TASKS and isinstance(category["name"], str) and isinstance(category["lead"], str):
            facts[key] = Fact(key, category["name"], "#tekhnika", category["lead"])
    regions = config.get("regions")
    if isinstance(regions, list) and all(isinstance(region, str) and len(region) < 40 for region in regions):
        facts["geo"] = Fact("geo", "Регіони робіт", "#geo",
                            f"{', '.join(regions)} області. Виїзд на конкретний об’єкт підтверджує диспетчер.")
    return facts


def _task(turns):
    for turn in reversed(turns):
        parts = CORRECTION.split(turn.casefold())
        latest = next((part for part in reversed(parts) if not NEGATED_TASK.search(part)), "")
        if "автокран" in latest:
            return "crane"
        if re.search(r"\bмул\b", latest):
            return "amph"
        if not EXPLICIT_TRANSPORT.search(latest) and any(term in latest for term in TASKS["materials"][0]):
            return "materials"
        for key, (terms, *_) in TASKS.items():
            if any(term in latest for term in terms):
                return key
    return None


def _place(turns, key):
    for turn in reversed(turns):
        parts = CORRECTION.split(turn)
        latest = parts[-1]
        if key == "trans" and (route := ROUTE.search(latest)):
            return f"{route[1]} → {route[2]}"[:160]
        candidates = LOCATION.findall(latest)
        if candidates:
            return candidates[-1][:160]
        short_place = re.split(r"[.,;!?]", latest, maxsplit=1)[0] if len(parts) > 1 else latest
        if len(short_place) <= 45 and re.fullmatch(_CITY, short_place) and any(
                word in short_place.lower() for word in ("полтав", "кременч", "київ", "харків", "черкас", "дніпр", "житомир")):
            return short_place
    return ""


def _latest(turns, pattern):
    for turn in reversed(turns):
        hit = pattern.search(CORRECTION.split(turn)[-1])
        if hit:
            return hit[0]
    return ""


def _question(key, turns, place):
    recent = " ".join(turns)
    if not place:
        return TASKS[key][3] if key == "trans" else "Де розташований об’єкт?"
    if key == "amph":
        if not ACCESS.search(recent):
            return TASKS[key][3]
        if not (QUANTITY.search(recent) or DETAILS.search(recent)):
            return "Яка приблизна площа водойми або ділянки, яку треба розчистити?"
    elif key == "trans":
        if " → " not in place:
            return "Який другий пункт маршруту?"
        if not _latest(turns, MASS):
            return "Які маса та габарити вантажу?"
    elif key == "crane":
        if not _latest(turns, MASS):
            return "Яку масу вантажу ви можете підтвердити?"
        if not _latest(turns, REACH):
            return "Який орієнтовний виліт від місця стоянки крана до точки підйому?"
    elif not QUANTITY.search(recent) and not DETAILS.search(recent):
        return TASKS[key][3]
    return ""


def _draft_comment(key, turns):
    details = (("Маса зі слів клієнта", MASS), ("Геометрія зі слів клієнта", REACH)) if key == "crane" else (
        ("Обсяг зі слів клієнта", VOLUME),) if key == "materials" else (("Параметр зі слів клієнта", QUANTITY),)
    return "\n".join(f"{label}: {value}" for label, pattern in details if (value := _latest(turns, pattern)))


class Support:
    max_body = MAX_BODY

    def __init__(self, root: Path, provider: Provider | None = None):
        self.root = root
        self.provider = provider
        self._model_lock = threading.Lock()
        self._model_turns = deque()

    def _model_budget(self):
        with self._model_lock:
            now = time.monotonic()
            while self._model_turns and now - self._model_turns[0] >= 600:
                self._model_turns.popleft()
            if len(self._model_turns) >= 50:
                return False
            self._model_turns.append(now)
            return True

    def status(self):
        return {"available": True, "mode": "model" if self.provider else "local",
                "attachments": self.provider is not None, "provider": "OpenAI" if self.provider else None}

    def reply(self, body):
        try:
            return 200, self.respond(body)
        except InputError as error:
            return 422, {"ok": False, "error": str(error)}
        except (OSError, ValueError, KeyError, TypeError):
            return 503, {"ok": False, "error": "unavailable"}

    def respond(self, body):
        if not isinstance(body, dict) or not body.keys() <= {"message", "history", "attachment", "consent"}:
            raise InputError("validation")
        message = _text(body.get("message", ""), MESSAGE_MAX)
        history = body.get("history", [])
        consent = body.get("consent", False)
        if not isinstance(history, list) or len(history) > HISTORY_MAX or not isinstance(consent, bool):
            raise InputError("validation")
        history = [_text(item, MESSAGE_MAX) for item in history]
        attachment = _attachment(body.get("attachment"), consent, self.provider)
        if not message and attachment is None:
            raise InputError("empty")
        facts = _facts(self.root)
        local = self._local(message, history, facts)
        if attachment is None and (local["handoff"] or not consent or self.provider is None):
            return local
        if attachment is not None and local["handoff"]:
            return local
        if not self._model_budget():
            if attachment is not None:
                local["reply"] = "Опрацювання файлів тимчасово зайняте. Можна продовжити текстом."
            return local
        projected = [fact.for_provider() for fact in facts.values()]
        try:
            answer, transcript = self.provider.answer(
                redact_contacts(message),
                [redact_contacts(item) for item in history], attachment, projected)
            reply, ids = answer["reply"], answer["fact_ids"]
            if (not isinstance(reply, str) or not reply.strip() or len(reply) > 1400 or
                    CLOUD_COMMITMENT.search(reply) or CONTACT_PATTERN.search(reply) or
                    not isinstance(ids, list) or len(ids) > 3 or
                    not all(isinstance(key, str) and key in facts for key in ids)):
                raise ProviderError()
            if transcript:
                transcript = redact_contacts(_text(transcript, TRANSCRIPT_MAX))
                local = self._local(transcript + ("\n" + message if message else ""), history, facts)
                if local["handoff"]:
                    return {**local, "transcript": transcript}
            if local["draft"] is None and attachment is not None and attachment[0].startswith("image/"):
                categories = {key for key in ids if key in TASKS}
                if len(categories) == 1:
                    category = categories.pop()
                    _, kind, subject, _ = TASKS[category]
                    local["draft"] = {"type": kind, "subject": subject, "place": "", "comment": ""}
            return {**local, "reply": reply.strip(), "mode": "model",
                    "sources": self._sources(dict.fromkeys(ids), facts),
                    **({"transcript": transcript} if transcript else {})}
        except (ProviderError, InputError, TypeError, KeyError):
            if attachment is not None:
                local["reply"] = "Не вдалося опрацювати файл. Опишіть задачу текстом або зверніться до диспетчера."
            return local

    @staticmethod
    def _sources(ids, facts):
        return [{"label": facts[key].label, "href": facts[key].href} for key in ids if key in facts]

    def _local(self, message, history, facts):
        turns = [*history, message]
        key = _task(turns)
        place = _place(turns, key)
        question = _question(key, turns, place) if key else ""
        draft = None
        if key:
            _, kind, subject, _ = TASKS[key]
            draft = {"type": kind, "subject": subject, "place": place, "comment": _draft_comment(key, turns)}
        handoff = False
        ids = [key] if key else []
        if OPERATOR_HANDOFF.search(message) or (HUMAN.search(message) and HUMAN_INTENT.search(message)) or REPEAT.search(message) or sum(
                item.casefold() == message.casefold() for item in history[-3:]) >= 2:
            handoff, ids = True, ["request"]
            reply = "Диспетчер може продовжити з чернетки. У розділі заявки є також контакт для прямої розмови."
        elif DANGER.search(message):
            handoff, ids = True, ["dispatch", "request"]
            reply = "Без огляду об’єкта й робочих параметрів безпечність робіт визначити неможливо. Потрібна оцінка фахівця на місці."
        elif PRICE.search(message) or BOOKING.search(message):
            handoff = True
            ids = ["price" if PRICE.search(message) else "dispatch", *ids]
            reply = facts[ids[0]].text
            if question:
                reply += " " + question
        elif COVERAGE.search(message) and "geo" in facts:
            ids = ["geo"]
            reply = facts["geo"].text
        elif key and key in facts:
            reply = ("Для підйому мають значення маса вантажу, виліт і майданчик."
                     if key == "crane" else facts[key].text)
            reply += " " + (question or "У чернетці вже є тип роботи й місце. Перевірте їх перед переходом до заявки.")
        else:
            ids = ["request"]
            reply = ("Розкажіть, що має статися на об’єкті: викопати, підняти, перевезти чи доставити матеріал. "
                     "Якщо вже відоме місце, додайте його.")
        return {"ok": True, "reply": reply, "sources": self._sources(ids, facts),
                "draft": draft, "handoff": handoff, "mode": "local"}
