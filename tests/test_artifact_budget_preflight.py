"""Synthetic, byte-based falsifiers for the multifile export audit."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.artifact_budget import DEFAULT_LIMIT, audit_artifact

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def artifact(tmp_path):
    p = tmp_path / "artifact"
    (p / "media").mkdir(parents=True)
    (p / "index.html").write_text("<main>Привіт</main>", encoding="utf-8")
    (p / "media" / "a.mp4").write_bytes(b"synthetic video\x00")
    return p


def test_real_utf8_bytes_and_digest(artifact):
    result = audit_artifact(artifact)
    assert result["ok"] and result["asset_count"] == 2
    assert result["total_bytes"] == sum(x["bytes"] for x in result["files"])
    assert result["media_bytes"] == len(b"synthetic video\x00")
    html = next(x for x in result["files"] if x["path"] == "index.html")
    assert html["bytes"] == len("<main>Привіт</main>".encode("utf-8"))
    assert html["sha256"] == hashlib.sha256((artifact / "index.html").read_bytes()).hexdigest()
    assert result["measurement_type"] == "on-disk artifact bytes; not transfer or render metrics"


def test_exact_boundary_and_one_byte_over(artifact):
    total = audit_artifact(artifact)["total_bytes"]
    assert audit_artifact(artifact, total)["ok"]
    denied = audit_artifact(artifact, total - 1)
    assert not denied["ok"] and denied["over_budget_bytes"] == 1


@pytest.mark.parametrize("limit", [True, False, 0, -1, 1.5, "67108864", None])
def test_bad_limit_fails_closed(artifact, limit):
    with pytest.raises(ValueError):
        audit_artifact(artifact, limit)


def test_missing_index_denied(artifact):
    (artifact / "index.html").unlink()
    with pytest.raises(ValueError, match="index.html"):
        audit_artifact(artifact)


@pytest.mark.parametrize("kind", ["file", "directory"])
def test_symlinks_cannot_hide_external_bytes(artifact, tmp_path, kind):
    outside = tmp_path / "external"
    outside.mkdir()
    (outside / "hidden.mp4").write_bytes(b"x" * 8)
    if kind == "file":
        (artifact / "media" / "external.mp4").symlink_to(outside / "hidden.mp4")
    else:
        (artifact / "media" / "external").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        audit_artifact(artifact)


def test_deterministic_sorted_inventory_and_largest(artifact):
    before = audit_artifact(artifact)
    after = audit_artifact(artifact)
    assert before == after
    assert [item["path"] for item in before["files"]] == ["index.html", "media/a.mp4"]
    assert before["largest"][0]["path"] == "index.html"


def test_cli_fails_on_over_budget_and_writes_inspectable_evidence(artifact, tmp_path):
    out = tmp_path / "report.json"
    run = subprocess.run([sys.executable, str(ROOT / "tools/artifact_budget.py"),
                          "--root", str(artifact), "--limit", "5", "--report", str(out)],
                         cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert run.returncode == 1
    report = json.loads(out.read_text(encoding="utf-8"))
    assert not report["ok"] and report["total_bytes"] > 5
    assert all(len(row["sha256"]) == 64 for row in report["files"])
    assert json.loads(run.stdout)["over_budget_bytes"] == report["over_budget_bytes"]


def test_cli_success_does_not_claim_release_readiness(artifact):
    run = subprocess.run([sys.executable, str(ROOT / "tools/artifact_budget.py"),
                          "--root", str(artifact)], cwd=ROOT, capture_output=True,
                         text=True, timeout=10)
    assert run.returncode == 0
    report = json.loads(run.stdout)
    assert report["ok"] and report["limit_bytes"] == DEFAULT_LIMIT
    assert "release" not in report
