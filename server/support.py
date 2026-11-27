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
    from .support_intake import EXPLANATIONS, LABELS, MAX_MEMORY, TASKS, Brief, BriefMemory, advance, plan
    from .support_provider import CONTACT_PATTERN, TRANSCRIPT_MAX, ProviderError, redact_contacts
else:
    from support_intake import EXPLANATIONS, LABELS, MAX_MEMORY, TASKS, Brief, BriefMemory, advance, plan
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

HUMAN = re.compile(r"\b(?:диспетчер\w*|менеджер\w*|людин\w*|человек\w*)\b", re.I)
HUMAN_INTENT = re.compile(r"\b(?:поклич|дайте|дай|з'єднай|з’єднай|підключ|хочу|можна|поговор|зв'яз|зв’яз|зв'яж|зв’яж|контакт|телефон|номер)\w*\b", re.I)
OPERATOR_HANDOFF = re.compile(r"живого\s+оператора|реальн\w+\s+оператора|\b(?:поклич|з'єднай|з’єднай|підключ|дайте|дай)\w*\s+(?:мені\s+)?оператора\b", re.I)
CONTACT_QUERY = re.compile(r"\b(?:як\s+(?:із вами\s+|з вами\s+)?зв[’'ʼ]язатися|ваш\s+(?:номер|телефон)|ваша\s+пошта|де\s+контакти)\b", re.I)
PRICE = re.compile(r"\bцін(?:а|и|у|ою|і|ах|ам)\b|скільки кошту|сколько сто|прайс|тариф|вартіст|кошторис|\bгрн\b", re.I)
BOOKING = re.compile(r"брон\w*|наявн\w*|вільн\w*|свобод\w*|\b(?:буде|є)\s+.{0,20}\b(?:завтра|сьогодні)\b|(?:статус|де\s+моя|що\s+з\s+моєю)\s+заяв", re.I)
DANGER = re.compile(r"безпек|безпечн|вантажопідйом|можна підняти|чи підніме|выдержит|строп|електроліні|леп\b|обвал|аварі|травм", re.I)
COVERAGE = re.compile(r"географ|виїжджає|виїжджа|обслуговуєте|працюєте.{0,20}\b(?:у|в|по)\b|област\w*.*працю", re.I)
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


class Support:
    max_body = MAX_BODY

    def __init__(self, root: Path, provider: Provider | None = None):
        self.root = root
        self.provider = provider
        self._memory = BriefMemory()
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
        if not isinstance(body, dict) or not body.keys() <= {"message", "history", "attachment", "consent", "memory"}:
            raise InputError("validation")
        message = _text(body.get("message", ""), MESSAGE_MAX)
        history = body.get("history", [])
        consent = body.get("consent", False)
        if not isinstance(history, list) or len(history) > HISTORY_MAX or not isinstance(consent, bool):
            raise InputError("validation")
        history = [_text(item, MESSAGE_MAX) for item in history]
        token = _text(body.get("memory", ""), MAX_MEMORY)
        prior = self._memory.unpack(token)
        expired = bool(token and prior is None)
        if prior is None:
            prior = Brief()
            if not expired:
                for line in history:
                    prior, _, _ = advance(prior, redact_contacts(line))
                    prior.specialist = prior.specialist or bool(DANGER.search(line))
        attachment = _attachment(body.get("attachment"), consent, self.provider)
        if not message and attachment is None:
            raise InputError("empty")
        facts = _facts(self.root)
        local = self._local(message, history, facts, prior)
        if attachment is not None:
            local["media"] = {"status": "unprocessed"}
        if expired:
            local["brief"]["reset"] = True
            local["reply"] = "Попередній контекст більше недоступний. Почнімо з цієї репліки. " + local["reply"]
            return local
        if attachment is None and (local["handoff"] or not consent or self.provider is None):
            return local
        if attachment is not None and local["handoff"]:
            local["reply"] += " Файл не опрацьовано. Його можна показати диспетчеру."
            return local
        if not self._model_budget():
            if attachment is not None:
                local["reply"] = "Опрацювання файлів тимчасово зайняте. Можна продовжити текстом."
            return local
        projected = [fact.for_provider() for fact in facts.values()]
        known = "; ".join(f"{field['label']}: {field['value']}" for field in local["brief"]["known"])
        provider_message = redact_contacts(message)
        if known:
            provider_message += "\n\nПідтверджені лише зі слів клієнта параметри задачі: " + known
        if pending := local["brief"]["next"]:
            provider_message += "\nНаступний незаповнений параметр: " + pending["label"]
        try:
            answer, transcript = self.provider.answer(
                provider_message,
                [redact_contacts(item) for item in history], attachment, projected)
            reply, ids = answer["reply"], answer["fact_ids"]
            if (not isinstance(reply, str) or not reply.strip() or len(reply) > 1400 or
                    CLOUD_COMMITMENT.search(reply) or CONTACT_PATTERN.search(reply) or
                    not isinstance(ids, list) or len(ids) > 3 or
                    not all(isinstance(key, str) and key in facts for key in ids)):
                raise ProviderError()
            if transcript:
                transcript = redact_contacts(_text(transcript, TRANSCRIPT_MAX))
                spoken, _, spoken_reset = advance(prior, transcript, source="transcript")
                spoken.specialist = spoken.specialist or bool(DANGER.search(transcript))
                local = self._local(message, history, facts, spoken)
                local["brief"]["reset"] = local["brief"]["reset"] or spoken_reset
                if local["handoff"]:
                    return {**local, "transcript": transcript, "media": {"status": "used"}}
            picked = [key for key in dict.fromkeys(ids) if key in TASKS]
            if local["draft"] is None and len(picked) == 1:
                subject = TASKS[picked[0]][2].lower()
                proposed = self._memory.unpack(local["memory"]) or Brief()
                proposed.proposal = picked[0]
                reset = local["brief"]["reset"]
                local["brief"] = proposed.view(False, {})
                local["brief"]["reset"] = reset
                local["memory"] = self._memory.pack(proposed)
                local["reply"] = f"Можливий напрям — {subject}. Це відповідає вашій задачі?"
            # Model text is never a customer-facing business statement. It supplies references and a hypothesis.
            result = {**local, "mode": "model", "sources": self._sources(dict.fromkeys(ids), facts) or local["sources"]}
            if attachment is not None:
                result["media"] = {"status": "used"}
            if transcript:
                result["transcript"] = transcript
            return result
        except (ProviderError, InputError, TypeError, KeyError):
            if attachment is not None:
                local["reply"] = "Не вдалося опрацювати файл. Опишіть задачу текстом або зверніться до диспетчера."
            return local

    @staticmethod
    def _sources(ids, facts):
        return [{"label": facts[key].label, "href": facts[key].href} for key in ids if key in facts]

    def _local(self, message, history, facts, prior):
        working, changes, reset = advance(prior, redact_contacts(message))
        key = working.task
        step = plan(working)
        question = step.question if step else ""
        working.specialist = working.specialist or bool(DANGER.search(message))
        handoff = False
        ids = [key] if key else []
        repeated = len(message.split()) >= 2 and sum(
            item.casefold() == message.casefold() for item in history[-3:]) >= 2
        contact = (CONTACT_QUERY.search(message) or OPERATOR_HANDOFF.search(message)
                   or (HUMAN.search(message) and HUMAN_INTENT.search(message)))
        if working.specialist:
            handoff, ids = True, ["dispatch", "request"]
            reply = ("Підйом чи роботу в цих умовах має оцінити фахівець на місці за даними об’єкта."
                     if DANGER.search(message) else
                     "У цій задачі лишається вимога огляду фахівцем. Диспетчер може продовжити з чернетки.")
        elif contact or REPEAT.search(message) or repeated:
            handoff, ids = True, ["request"]
            reply = "Диспетчер може продовжити з чернетки. У розділі заявки є також контакт для прямої розмови."
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
            parts = []
            if reset:
                parts.append("Починаю окрему чернетку для цієї задачі.")
            if changes:
                updated = ", ".join(f"{LABELS[name].lower()} — {value}" for name, value in changes.items())
                parts.append(f"Оновив у чернетці: {updated}.")
            elif prior.task == key and question:
                added = {name: value for name, value in working.values.items() if name not in prior.values}
                if added:
                    recorded = ", ".join(f"{LABELS[name].lower()} — {value}" for name, value in added.items())
                    parts.append(f"Записав: {recorded}.")
            if prior.task != key:
                parts.append(EXPLANATIONS.get(key, facts[key].text))
            if "secondary" in working.values and "secondary" not in prior.values:
                parts.append("У чернетці врахував також вивезення ґрунту.")
            if question:
                if working.skipped != prior.skipped:
                    parts.append("Цей параметр лишу для уточнення диспетчером.")
                parts.append(question)
            elif working.unresolved():
                ids.append("request")
                handoff = True
                parts.append("У чернетці відмітив, що потрібно уточнити з диспетчером.")
            else:
                summary = ", ".join(dict.fromkeys(value for name, value in working.values.items() if name != "secondary"))
                if summary and not changes:
                    parts.append(f"Зафіксував: {summary}.")
                parts.append("Чернетку можна звірити й передати диспетчеру.")
                if key == "crane":
                    parts.append("Підбір крана підтвердить диспетчер.")
            reply = " ".join(parts)
        else:
            ids = ["request"]
            reply = "Що потрібно зробити на об’єкті? Наприклад, викопати траншею, підняти вантаж або доставити матеріал."
        view = working.view(handoff, changes)
        view["reset"] = reset
        if handoff and not working.specialist and question and (PRICE.search(message) or BOOKING.search(message)):
            view["next"] = step.view()
        return {"ok": True, "reply": reply, "sources": self._sources(ids, facts),
                "draft": working.draft(), "handoff": handoff, "mode": "local",
                "brief": view, "memory": self._memory.pack(working)}
