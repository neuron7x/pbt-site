"""Run the real evidence packaging step in an isolated synthetic Git repository."""
import os
from pathlib import Path
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]


def git(repository, *arguments):
    return subprocess.check_output(["git", *arguments], cwd=repository, text=True).strip()


def test_workflow_proof_bundle_restores_the_exact_commit_and_rejects_corruption(tmp_path):
    workflow = yaml.safe_load((ROOT / ".github/workflows/evidence-closure.yml").read_text(encoding="utf-8"))
    steps = [step for job in workflow["jobs"].values() for step in job["steps"]
             if step.get("name") == "Package and restore the exact reconciled Git commit"]
    assert len(steps) == 1
    workspace = tmp_path / "working checkout"
    report = tmp_path / "report"
    runner = tmp_path / "runner"
    for path in (workspace, report, runner):
        path.mkdir()
    git(workspace, "init", "-q")
    (workspace / "source.txt").write_text("source\n", encoding="utf-8")
    git(workspace, "add", "source.txt")
    identity = ("-c", "user.name=Test", "-c", "user.email=test@example.invalid")
    git(workspace, *identity, "commit", "-qm", "source")
    source = git(workspace, "rev-parse", "HEAD")
    (workspace / "receipt.json").write_text('{"status":"synthetic"}\n', encoding="utf-8")
    git(workspace, "add", "receipt.json")
    git(workspace, *identity, "commit", "-qm", "proof")
    proof = git(workspace, "rev-parse", "HEAD")
    (report / "proof-local-commit-sha.txt").write_text(proof + "\n", encoding="utf-8")

    env = {**os.environ, "SOURCE_SHA": source, "GITHUB_WORKSPACE": str(workspace),
           "REPORT_DIR": str(report), "RUNNER_TEMP": str(runner)}
    result = subprocess.run(["bash", "-euo", "pipefail", "-c", steps[0]["run"]],
                            cwd=workspace, env=env, text=True, capture_output=True, timeout=35)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert f"PROOF_RESTORED source={source} proof={proof}" in result.stdout
    assert "missing_source=rejected missing_pack=rejected truncated_pack=rejected" in result.stdout
    assert git(workspace, "bundle", "list-heads", str(runner / "pbt-validated-proof.bundle")) == (
        f"{proof} refs/pbt-proof/reconciled")
