"""Інваріанти матриці двох тем: 6 екранів, тільки справжні PNG."""
from io import BytesIO

import pytest
from PIL import Image

from tools import visual_contract as vc


def png(width=16, height=8):
    out = BytesIO()
    Image.new("RGB", (width, height), (245, 245, 242)).save(out, format="PNG")
    return out.getvalue()


def valid_probe():
    return {
        "theme": "sky", "quality": "static",
        "appearance": {
            "surface": "rgb(234, 247, 255)", "hero": "rgb(13, 106, 224)",
            "heading_font": "Tektur, system-ui", "cta_radius": "999px",
            "pressed": ["sky"],
        },
        "visible_h1": True, "visible_cta": True,
        "horizontal_overflow": False,
        "sections": list(vc.REQUIRED_SECTIONS),
        "broken_visible_images": [], "page_errors": [],
    }


def test_layout_hard_checks_are_fail_closed():
    assert vc.audit_layout(valid_probe()) == []
    probe = valid_probe()
    probe.update({
        "theme": "undefined", "quality": "full", "visible_h1": False,
        "horizontal_overflow": True, "sections": ["top"],
        "broken_visible_images": ["broken.webp"], "page_errors": ["ReferenceError"],
    })
    assert len(vc.audit_layout(probe)) == 7


def test_both_theme_appearances_are_checked_not_just_data_attribute():
    baseline = valid_probe()
    assert vc.audit_layout(baseline) == []
    counterfeit = {**baseline, "theme": "precision"}
    errors = vc.audit_layout(counterfeit)
    assert len(errors) >= 4 and any("aria-pressed" in err for err in errors)
    correct = {**baseline, "theme": "precision", "appearance": {
        "surface": "rgb(245, 245, 242)", "hero": "rgb(16, 24, 32)",
        "heading_font": "IBM Plex Sans, system-ui", "cta_radius": "5px",
        "pressed": ["precision"],
    }}
    assert vc.audit_layout(correct) == []


def test_png_sha_crc_and_complete_two_theme_matrix(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VIEWPORTS", (("small", 16, 8, False, ("top",)),))
    raw = png()
    records = []
    for theme in vc.THEMES:
        name = f"{theme}--small--top.png"
        records.append(vc.capture_record(raw, name, "small", "top", 16, 8, theme))
        (tmp_path / name).write_bytes(raw)
    report = {"schema_version": vc.SCHEMA_VERSION, "captures": records}
    assert vc.verify_capture_manifest(report, tmp_path) == []
    assert all(len(r["sha256"]) == 64 and r["bytes"] == len(raw) for r in records)

    incomplete = {"schema_version": vc.SCHEMA_VERSION, "captures": records[:1]}
    assert any("Неповна матриця" in err for err in vc.verify_capture_manifest(incomplete, tmp_path))
    malformed = {"schema_version": vc.SCHEMA_VERSION, "captures": [{**records[0], "filename": "../bad.png"}]}
    assert vc.verify_capture_manifest(malformed, tmp_path)
    duplicated = {"schema_version": vc.SCHEMA_VERSION, "captures": records + records[:1]}
    assert any("повторене" in err for err in vc.verify_capture_manifest(duplicated, tmp_path))
    another = BytesIO()
    Image.new("RGB", (16, 8), (0, 0, 0)).save(another, format="PNG")
    # Валідний PNG, але інші пікселі: саме хеш викриває підміну.
    (tmp_path / "sky--small--top.png").write_bytes(another.getvalue())
    assert any("sha256" in err for err in vc.verify_capture_manifest(report, tmp_path))
    # Коректний вміст + довільний хвіст: парсер відхиляє ще до перевірки SHA.
    (tmp_path / "sky--small--top.png").write_bytes(raw + b"mutated")
    assert any("Не PNG" in err for err in vc.verify_capture_manifest(report, tmp_path))


def test_png_crc_is_actually_checked():
    content = bytearray(png())
    # Змінюємо тільки CRC IEND: довжина, тип і дані чанка лишаються валідними.
    content[-1] ^= 0xFF
    with pytest.raises(ValueError, match="PNG CRC32 mismatch: IEND"):
        vc.png_dimensions(bytes(content))
    with pytest.raises(ValueError):
        vc.capture_record(b"<html>fake</html>", "sky--fake.png", "small", "top", 16, 8)
    with pytest.raises(ValueError):
        vc.png_dimensions(png()[:-12])  # truncated IEND
    with pytest.raises(ValueError):
        vc.png_dimensions(png() + b"hidden payload")  # trailing bytes


def test_dimensions_must_match_css_viewport():
    with pytest.raises(ValueError):
        vc.capture_record(png(12, 8), "sky--wrong.png", "small", "top", 16, 8)


def test_manifest_rejects_complete_counterfeit_geometry_with_consistent_metadata(tmp_path):
    """Узгоджені PNG/metadata/SHA не можуть замінити канонічні розміри екранів."""
    records = []
    for theme in vc.THEMES:
        for viewport, width, height, _, sections in vc.VIEWPORTS:
            raw = png(width, height)
            for section in sections:
                name = f"{theme}--{viewport}--{section}.png"
                (tmp_path / name).write_bytes(raw)
                records.append(vc.capture_record(raw, name, viewport, section, width, height, theme))
    report = {"schema_version": vc.SCHEMA_VERSION, "captures": records}
    assert len(records) == 32
    assert vc.verify_capture_manifest(report, tmp_path) == []

    raw = png(1, 1)
    for i, rec in enumerate(records):
        (tmp_path / rec["filename"]).write_bytes(raw)
        # Оновлюємо і розміри, і байти, і SHA: тест має спрацювати саме на профілі.
        records[i] = vc.capture_record(raw, rec["filename"], rec["viewport"], rec["section"], 1, 1, rec["theme"])
    failures = vc.verify_capture_manifest(report, tmp_path)
    assert len(failures) == len(records)
    assert all("канонічному екрану" in failure for failure in failures)


def test_matrix_has_exactly_six_profiles_for_each_theme():
    names = [x[0] for x in vc.VIEWPORTS]
    assert len(names) == len(set(names)) == 6
    assert vc.THEMES == ("sky", "precision")
    assert any(width == 320 and mobile for _, width, _, mobile, _ in vc.VIEWPORTS)
    assert all("top" in scenes for _, _, _, _, scenes in vc.VIEWPORTS)
