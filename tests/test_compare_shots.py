"""Візуальні різниці лише між валідними кадрами тієї самої теми."""
from io import BytesIO
import json

import pytest
from PIL import Image

from tools import compare_shots as cs, visual_contract as vc


def png(color):
    stream = BytesIO()
    Image.new("RGB", (16, 8), color).save(stream, format="PNG")
    return stream.getvalue()


def write_evidence(folder, revision, raw):
    folder.mkdir()
    records = []
    for theme in vc.THEMES:
        name = f"{theme}--tiny--top.png"
        (folder / name).write_bytes(raw)
        records.append(vc.capture_record(raw, name, "tiny", "top", 16, 8, theme))
    (folder / "manifest.json").write_text(json.dumps({
        "schema_version": vc.SCHEMA_VERSION,
        "revision": revision, "browser": {"engine": "chromium", "version": "test"},
        "field_lcp_ms": None, "field_inp_ms": None, "field_cls": None,
        "failures": [], "captures": records,
    }), encoding="utf-8")


def test_true_pixel_metrics_for_both_themes_and_contact_sheets(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VIEWPORTS", (("tiny", 16, 8, False, ("top",)),))
    monkeypatch.setattr(cs, "PREVIEWS", {(t, "tiny", "top") for t in vc.THEMES})
    base, candidate, out = (tmp_path / x for x in ("base", "new", "diff"))
    write_evidence(base, "old", png((0, 0, 0)))
    write_evidence(candidate, "new", png((255, 255, 255)))
    report = cs.compare(base, candidate, out)
    assert report["screenshots_compared"] == 2
    assert {row["theme"] for row in report["comparisons"]} == set(vc.THEMES)
    assert all(row["mean_absolute_luma_difference"] == 255 for row in report["comparisons"])
    assert all(row["changed_pixel_fraction_above_15"] == 1 for row in report["comparisons"])
    for theme in vc.THEMES:
        file = out / f"compare--{theme}--tiny--top.png"
        assert file.is_file()
        assert Image.open(file).size == (48, 8)
    assert "не оцінка краси" in (out / "README.md").read_text(encoding="utf-8")


def test_no_change_has_exact_zero_difference():
    with Image.open(BytesIO(png((25, 30, 35)))) as image:
        result, _ = cs.image_difference(image, image)
    assert result["mean_absolute_luma_difference"] == 0
    assert result["changed_pixel_fraction_above_15"] == 0


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
    (candidate / "precision--tiny--top.png").write_bytes(b"not a screenshot")
    with pytest.raises(ValueError, match="Неприйнятні докази"):
        cs.compare(base, candidate, tmp_path / "out")
