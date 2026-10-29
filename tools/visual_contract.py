"""Контракт доказових знімків ПБТ.

Тільки детерміновані правила; жодних Lighthouse-сурогатів, трекерів,
вимірів INP без реальної взаємодії чи вигаданих оцінок преміальності.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

SCHEMA_VERSION = 2
THEMES = ('sky', 'precision')
REQUIRED_SECTIONS = (
    "top", "roboty", "masshtab", "tekhnika", "cina",
    "materialy", "dokaz", "geo", "zapyt",
)
# CSS-пікселі; знімки усіх профілів з reduced-motion для відтворюваності.
VIEWPORTS = (
    ("desktop-1440", 1440, 900, False, ("top", "roboty", "tekhnika", "cina", "dokaz", "zapyt")),
    ("desktop-1366-low", 1366, 650, False, ("top",)),
    ("desktop-1024", 1024, 768, False, ("top", "tekhnika")),
    ("tablet-820", 820, 1180, True, ("top",)),
    ("mobile-390", 390, 844, True, ("top", "roboty", "tekhnika", "cina", "zapyt")),
    ("mobile-320", 320, 568, True, ("top",)),
)


def png_dimensions(content: bytes) -> tuple[int, int]:
    """Pillow перевіряє справжній PNG, зокрема CRC, а не тільки магічні байти."""
    try:
        with Image.open(BytesIO(content)) as img:
            if img.format != "PNG":
                raise ValueError("Очікується PNG")
            size = img.size
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValueError(f"Пошкоджений PNG: {exc}") from exc
    if not (0 < size[0] <= 20000 and 0 < size[1] <= 20000):
        raise ValueError("Недопустимий розмір PNG")
    return size

def capture_record(content: bytes, name: str, viewport: str, section: str, width: int, height: int, theme: str = 'sky') -> dict:
    if theme not in THEMES:
        raise ValueError("Непідтримувана тема: " + theme)
    w, h = png_dimensions(content)
    if (w, h) != (width, height):
        raise ValueError(f"{name}: фактичні пікселі {w}x{h}, очікували {width}x{height}")
    return {
        "filename": name,
        "viewport": viewport,
        "theme": theme,
        "section": section,
        "width": w,
        "height": h,
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def audit_layout(probe: dict) -> list[str]:
    """Без здогадів про розміри елементів: лише машинно-видимі порушення."""
    failures = []
    if probe.get("theme") not in THEMES:
        failures.append("Тема не визначена або невалідна")
    if probe.get("quality") != "static":
        failures.append("Потрібен статичний reduced-motion профіль")
    if not probe.get("visible_h1"):
        failures.append("Головний заголовок прихований")
    if not probe.get("visible_cta"):
        failures.append("Заклик до заявки прихований")
    if probe.get("horizontal_overflow"):
        failures.append("Горизонтальний скрол")
    missing = sorted(set(REQUIRED_SECTIONS) - set(probe.get("sections", ())))
    if missing:
        failures.append("Відсутні секції: " + ", ".join(missing))
    if probe.get("broken_visible_images"):
        failures.append("Не завантажено видимі зображення: " + ", ".join(probe["broken_visible_images"]))
    if probe.get("page_errors"):
        failures.append("Помилки JavaScript: " + "; ".join(probe["page_errors"]))
    return failures


def verify_capture_manifest(report: dict, directory: Path) -> list[str]:
    """Текст/JSON не достатній: файли мають реально існувати й збігатися за хешем."""
    failures = []
    if report.get("schema_version") != SCHEMA_VERSION:
        failures.append("Невідома версія маніфесту")
    names = set()
    expected = {(theme, v[0], section) for theme in THEMES for v in VIEWPORTS for section in v[4]}
    observed = set()
    for rec in report.get("captures", []):
        name = rec.get("filename", "")
        if name in names or Path(name).name != name or not name.endswith(".png"):
            failures.append("Невалідне чи повторене ім'я PNG: " + name)
            continue
        names.add(name)
        observed.add((rec.get("theme"), rec.get("viewport"), rec.get("section")))
        if name != f"{rec.get('theme')}--{rec.get('viewport')}--{rec.get('section')}.png":
            failures.append("Ім’я PNG не збігається з темою/екраном/секцією: " + name)
        p = directory / name
        if not p.is_file():
            failures.append("Немає файла: " + name)
            continue
        try:
            raw = p.read_bytes()
            size = png_dimensions(raw)
            if (rec.get("width"), rec.get("height")) != size:
                failures.append("Помилковий розмір: " + name)
            if len(raw) != rec.get("bytes") or hashlib.sha256(raw).hexdigest() != rec.get("sha256"):
                failures.append("Помилка sha256 або кількості байтів: " + name)
        except ValueError:
            failures.append("Не PNG: " + name)
    if observed != expected:
        failures.append("Неповна матриця знімків: " + repr(sorted(expected - observed)))
    return failures
