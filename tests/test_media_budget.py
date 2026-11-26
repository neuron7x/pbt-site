"""Розмір і походження байтів: budget фальсифікується файлом, не словами."""

import json
from collections import Counter
from pathlib import Path

from tools.media_budget import audit_media

ROOT = Path(__file__).resolve().parent.parent
BUDGET = json.loads((ROOT / "config" / "visual-budgets.json").read_text(encoding="utf-8"))


def tiny_rules():
    return {
        "schema_version": 1, "max_total_bytes": 30, "max_single_asset_bytes": 20,
        "rules": [{"glob": "park/*.webp", "min_count": 2, "max_bytes": 12}],
    }


def test_media_budget_accepts_small_valid_pack(tmp_path):
    d = tmp_path / "park"
    d.mkdir()
    (d / "one.webp").write_bytes(b"abc")
    (d / "two.webp").write_bytes(b"123456789")
    result = audit_media(tmp_path, tiny_rules())
    assert result["failures"] == []
    assert result["total_bytes"] == 12
    assert result["media_files"] == 2
    assert result["files"][0]["sha256"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert len(result["files"][1]["sha256"]) == 64


def test_media_budget_detects_oversize_and_missing_assets(tmp_path):
    d = tmp_path / "park"
    d.mkdir()
    (d / "too-big.webp").write_bytes(b"x" * 25)
    result = audit_media(tmp_path, tiny_rules())
    assert any("too-big.webp" in x for x in result["failures"])
    assert any("Відсутні активи" in x for x in result["failures"])


def test_media_budget_rejects_escape_globs_and_missing_required_categories(tmp_path):
    settings = tiny_rules()
    settings["rules"].append({"glob": "../outside/*", "min_count": 1, "max_bytes": 5})
    result = audit_media(tmp_path, settings)
    assert any("Невалідне правило" in x for x in result["failures"])
    assert any("Відсутні активи" in x for x in result["failures"])


def test_repository_media_pack_within_explicit_baseline_regression_caps():
    result = audit_media(ROOT / "web" / "media", BUDGET)
    paths = [item["path"] for item in result["files"]]
    required = {"cine": 36, "logo": 13, "map": 3, "mat": 16, "park": 32, "svc": 6, "video": 42}
    counts = Counter(path.split("/", 1)[0] for path in paths)
    assert all(counts[group] >= minimum for group, minimum in required.items()), counts
    assert not any(path.startswith("logo/partners-") for path in paths)
    assert not result["failures"], result["failures"]
    # Ліміти на файлові активи НЕ дорівнюють мережевому завантаженню користувача.
    assert result["measurement_type"] == "repository file sizes, not network transfer"
