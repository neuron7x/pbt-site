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



def test_enforce_budget_writes_complete_report_before_rejecting(artifact, tmp_path):
    from tools.artifact_budget import enforce_artifact_budget
    report = tmp_path / "budget.json"
    total = audit_artifact(artifact)["total_bytes"]
    with pytest.raises(ValueError, match="exceeds"):
        enforce_artifact_budget(artifact, report, total - 1)
    observed = json.loads(report.read_text(encoding="utf-8"))
    assert observed["total_bytes"] == total
    assert observed["over_budget_bytes"] == 1
    assert observed["ok"] is False
    assert len(observed["files"]) == 2


def test_enforce_exact_cap_works_without_claiming_production_ready(artifact, tmp_path):
    from tools.artifact_budget import enforce_artifact_budget
    report = tmp_path / "budget.json"
    total = audit_artifact(artifact)["total_bytes"]
    result = enforce_artifact_budget(artifact, report, total)
    assert result["ok"] is True
    assert json.loads(report.read_text(encoding="utf-8"))["limit_bytes"] == total
    assert "production_ready" not in result


def test_report_replace_does_not_follow_preexisting_symlink(artifact, tmp_path):
    from tools.artifact_budget import enforce_artifact_budget
    target = tmp_path / "sensitive.txt"
    target.write_text("CANARY", encoding="utf-8")
    report = tmp_path / "budget.json"
    report.symlink_to(target)
    enforce_artifact_budget(artifact, report)
    assert target.read_text(encoding="utf-8") == "CANARY"
    assert report.is_file() and not report.is_symlink()


def test_real_multifile_builder_enforces_budget_after_copy():
    code = (ROOT / "tools/inline.py").read_text(encoding="utf-8")
    assert "from artifact_budget import enforce_artifact_budget" in code
    assert "budget = enforce_artifact_budget(MULTI, DIST / 'artifact-budget.json')" in code
    assert code.index("shutil.copy2(f, t)") < code.index("enforce_artifact_budget(MULTI")
    assert code.index("enforce_artifact_budget(MULTI") < code.index("print('artifact/'")
    assert "budget['total_bytes'] != tot" in code
    assert "budget['asset_count'] != n + 1" in code



def test_multifile_builder_keeps_source_bytes_and_fail_closed_size_gate():
    code = (ROOT / "tools/inline.py").read_text(encoding="utf-8")
    assert "preflight = audit_artifact(MULTI)" in code
    assert "DIST / 'artifact-budget-preflight.json'" in code
    assert "fit_copies(" not in code
    assert "from artifact_video_fit" not in code
    assert code.index('shutil.copy2(f, t)') < code.index('preflight = audit_artifact(MULTI)')
    assert code.index('preflight = audit_artifact(MULTI)') < code.index("enforce_artifact_budget(MULTI")
    assert code.index("tot = sum(") < code.index("enforce_artifact_budget(MULTI")



def test_provider_quality_uploads_real_multifile_budget_proof_without_changing_html_contract():
    workflow = (ROOT / ".github/workflows/pr-quality.yml").read_text(encoding="utf-8")
    assert workflow.count("artifacts/offline-bundles.sha256") == 2
    assert "test -s dist/artifact-budget-preflight.json" in workflow
    assert "test -s dist/artifact-budget.json" in workflow
    assert "artifacts/artifact-metrics.sha256" in workflow
    for name in ("dist/artifact-budget-preflight.json", "dist/artifact-budget.json", "dist/artifact-video-fit.json"):
        assert workflow.count(name) >= 2
    assert "if-no-files-found: error" in workflow
    assert workflow.index("test -s dist/artifact-budget.json") < workflow.index("Preserve full-suite report")
