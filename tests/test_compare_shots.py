"""Доказове pixel-by-pixel порівняння: лише сумісні, справжні PNG."""
from io import BytesIO
import json

import pytest
from PIL import Image

from tools import compare_shots as cs, visual_contract as vc


def png(color):
    buf = BytesIO()
    Image.new("RGB", (16, 8), color).save(buf, format="PNG")
    return buf.getvalue()


def write_evidence(folder, revision, raw):
    folder.mkdir()
    name = "tiny--top.png"
    (folder / name).write_bytes(raw)
    rec = vc.capture_record(raw, name, "tiny", "top", 16, 8)
    (folder / "manifest.json").write_text(json.dumps({
        "schema_version": 1, "revision": revision,
        "browser": {"engine": "chromium", "version": "test"},
        "field_lcp_ms": None, "field_inp_ms": None, "field_cls": None,
        "failures": [], "captures": [rec],
    }), encoding="utf-8")


def test_true_pixel_metrics_and_review_contact_sheet(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VIEWPORTS", (("tiny", 16, 8, False, ("top",)),))
    monkeypatch.setattr(cs, "PREVIEWS", {("tiny", "top")})
    base, candidate, out = (tmp_path / x for x in ("base", "new", "diff"))
    write_evidence(base, "old", png((0, 0, 0)))
    write_evidence(candidate, "new", png((255, 255, 255)))
    report = cs.compare(base, candidate, out)
    assert report["screenshots_compared"] == 1
    assert report["comparisons"][0]["mean_absolute_luma_difference"] == 255
    assert report["comparisons"][0]["changed_pixel_fraction_above_15"] == 1
    assert (out / "compare--tiny--top.png").is_file()
    assert Image.open(out / "compare--tiny--top.png").size == (48, 8)
    assert "не оцінка краси" in (out / "README.md").read_text(encoding="utf-8")


def test_no_change_has_exact_zero_difference():
    with Image.open(BytesIO(png((25, 30, 35)))) as image:
        values, _ = cs.image_difference(image, image)
    assert values["mean_absolute_luma_difference"] == 0
    assert values["changed_pixel_fraction_above_15"] == 0


def test_reject_browser_version_drift_and_tampering(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VIEWPORTS", (("tiny", 16, 8, False, ("top",)),))
    base, candidate = (tmp_path / x for x in ("base", "new"))
    write_evidence(base, "old", png("black"))
    write_evidence(candidate, "new", png("white"))
    manifest = candidate / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["browser"]["version"] = "different"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="версія браузера"):
        cs.compare(base, candidate, tmp_path / "out")
    data["browser"]["version"] = "test"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    (candidate / "tiny--top.png").write_bytes(b"not a screenshot")
    with pytest.raises(ValueError, match="Неприйнятні докази"):
        cs.compare(base, candidate, tmp_path / "out")
