"""Independent falsification of the post-capture evidence gate."""
import json
from io import BytesIO

import pytest
from PIL import Image

from tools import evidence_gate as eg
from tools import media_budget, visual_contract as vc

SHA = "a" * 40


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VIEWPORTS", (("tiny", 16, 12, False, ("top",)),))
    shots = tmp_path / "shots"
    shots.mkdir()
    raw = BytesIO()
    Image.new("RGB", (16, 12), (245, 245, 242)).save(raw, format="PNG")
    records, profiles = [], []
    for theme in vc.THEMES:
        filename = f"{theme}--tiny--top.png"
        blob = raw.getvalue()
        (shots / filename).write_bytes(blob)
        records.append(vc.capture_record(blob, filename, "tiny", "top", 16, 12, theme))
        if theme == "sky":
            appearance = {
                "surface": "rgb(234, 247, 255)", "hero": "rgb(13, 106, 224)",
                "heading_font": "Tektur", "cta_radius": "999px", "pressed": ["sky"],
            }
        else:
            appearance = {
                "surface": "rgb(245, 245, 242)", "hero": "rgb(16, 24, 32)",
                "heading_font": "IBM Plex Sans", "cta_radius": "5px",
                "pressed": ["precision"],
            }
        profiles.append({
            "theme": theme, "viewport": "tiny", "probe": {
                "theme": theme, "quality": "static", "appearance": appearance,
                "visible_h1": True, "visible_cta": True,
                "horizontal_overflow": False,
                "sections": list(vc.REQUIRED_SECTIONS),
                "broken_visible_images": [], "page_errors": [],
            },
        })
    report = {
        "schema_version": vc.SCHEMA_VERSION, "revision": SHA,
        "measurement_type": "laboratory screenshot audit; NOT field Core Web Vitals",
        "field_lcp_ms": None, "field_inp_ms": None, "field_cls": None,
        "browser": {"engine": "chromium", "version": "test"},
        "viewports": profiles, "captures": records, "failures": [],
    }
    manifest = shots / "manifest.json"
    manifest.write_text(json.dumps(report), encoding="utf-8")
    root = tmp_path / "media"
    root.mkdir()
    (root / "image.webp").write_bytes(b"small fixture")
    budget_file = tmp_path / "budget.json"
    budgets = {
        "schema_version": 1, "max_total_bytes": 100,
        "max_single_asset_bytes": 100,
        "rules": [{"glob": "*.webp", "max_bytes": 100, "min_count": 1}],
    }
    budget_file.write_text(json.dumps(budgets), encoding="utf-8")
    media = tmp_path / "media.json"
    media.write_text(json.dumps(media_budget.audit_media(root, budgets)), encoding="utf-8")
    return shots, media, root, budget_file, manifest


def check(evidence, sha=SHA):
    shots, report, root, budget, _ = evidence
    return eg.verify_evidence(shots, report, root, budget, sha)


def test_evidence_integrity_accepts_genuine_matching_proofs(evidence):
    result = check(evidence)
    assert result["ok"], result
    assert result["screenshot_count"] == 2
    assert set(result["evidence"]) == {"shots_manifest", "media_report"}


@pytest.mark.parametrize("change", ["sha", "field", "missing_profile", "claimed_success"])
def test_evidence_integrity_fails_closed_on_counterfeit_manifest(evidence, change):
    manifest = evidence[-1]
    report = json.loads(manifest.read_text(encoding="utf-8"))
    if change == "sha":
        report["revision"] = "b" * 40
    elif change == "field":
        report["field_inp_ms"] = 42
    elif change == "missing_profile":
        report["viewports"].pop()
    else:
        report["failures"] = ["browser crashed"]
    manifest.write_text(json.dumps(report), encoding="utf-8")
    assert not check(evidence)["ok"]


def test_evidence_integrity_rejects_corrupt_png(evidence):
    file = evidence[0] / "sky--tiny--top.png"
    file.write_bytes(file.read_bytes() + b"unexpected bytes")
    assert not check(evidence)["ok"]


def test_evidence_integrity_rejects_stale_media_and_missing_revision(evidence):
    (evidence[2] / "unexpected.mp4").write_bytes(b"unreported")
    result = check(evidence, sha="")
    assert not result["ok"]
    assert any("SHA" in failure for failure in result["failures"])
    assert any("recomputed" in failure for failure in result["failures"])
