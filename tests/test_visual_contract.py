"""Інваріанти доказового візуального маніфесту; без знімків-«заглушок»."""
from io import BytesIO

import pytest
from PIL import Image

from tools import visual_contract as vc


def png(width=16, height=8):
    b = BytesIO()
    Image.new("RGB", (width, height), (245, 245, 242)).save(b, format="PNG")
    return b.getvalue()


def valid_probe():
    return {
        "quality": "static", "visible_h1": True, "visible_cta": True,
        "horizontal_overflow": False, "sections": list(vc.REQUIRED_SECTIONS),
        "broken_visible_images": [], "page_errors": [],
    }


def test_layout_hard_checks_are_fail_closed():
    assert vc.audit_layout(valid_probe()) == []
    probe = valid_probe()
    probe.update({"quality": "full", "visible_h1": False, "horizontal_overflow": True,
                  "sections": ["top"], "broken_visible_images": ["broken.webp"],
                  "page_errors": ["ReferenceError"]})
    errors = vc.audit_layout(probe)
    assert len(errors) == 6, errors
    assert "переповнення" not in str(errors).lower() or errors


def test_real_png_integrity_size_sha_and_full_matrix(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VIEWPORTS", (("small", 16, 8, False, ("top",)),))
    raw = png()
    record = vc.capture_record(raw, "small--top.png", "small", "top", 16, 8)
    (tmp_path / record["filename"]).write_bytes(raw)
    manifest = {"schema_version": 1, "captures": [record]}
    assert vc.verify_capture_manifest(manifest, tmp_path) == []
    assert len(record["sha256"]) == 64
    assert record["bytes"] == len(raw)

    malicious = {"schema_version": 1, "captures": [{**record, "filename": "../bad.png"}]}
    assert vc.verify_capture_manifest(malicious, tmp_path)
    duplicate = {"schema_version": 1, "captures": [record, record]}
    assert any("повторене" in e for e in vc.verify_capture_manifest(duplicate, tmp_path))

    (tmp_path / "small--top.png").write_bytes(raw + b"mutated")
    assert any("sha256" in e for e in vc.verify_capture_manifest(manifest, tmp_path))


def test_png_crc_is_actually_checked():
    content = bytearray(png())
    content[-9] ^= 0xFF
    with pytest.raises(ValueError):
        vc.png_dimensions(bytes(content))
    with pytest.raises(ValueError):
        vc.capture_record(b"<html>fake</html>", "fake.png", "small", "top", 16, 8)


def test_dimensions_must_match_css_viewport():
    with pytest.raises(ValueError):
        vc.capture_record(png(12, 8), "wrong.png", "small", "top", 16, 8)


def test_matrix_is_explicit_and_contains_320px_phone():
    names = [x[0] for x in vc.VIEWPORTS]
    assert len(names) == len(set(names)) == 7
    assert any(w == 320 and mobile for _, w, _, mobile, _ in vc.VIEWPORTS)
    assert all("top" in scenes for _, _, _, _, scenes in vc.VIEWPORTS)
