"""The PR gate must verify the exact main base instead of treating green PR as its proxy."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_independent_main_baseline_gate_is_source_pinned_and_uploads_proof():
    workflow = (ROOT / '.github/workflows/pr-quality.yml').read_text()
    assert 'baseline-control:' in workflow
    assert 'Independent exact-main make gate' in workflow
    assert 'PBT_BASE_SHA: ${{ github.event.pull_request.base.sha }}' in workflow
    assert 'ref: ${{ github.event.pull_request.base.sha }}' in workflow
    assert 'test "$(git rev-parse HEAD)" = "$PBT_BASE_SHA"' in workflow
    assert 'Run unchanged main make gate at its immutable SHA' in workflow
    assert 'test -s artifacts/base-junit.xml' in workflow
    assert 'artifacts/base-commit.txt' in workflow
    assert 'if-no-files-found: error' in workflow
    assert "  push:\n    branches: [main]\n" in workflow
    assert ("  baseline-control:\n"
            "    name: Independent exact-main make gate (no main mutation)\n"
            "    if: github.event_name == 'pull_request'") in workflow
    assert 'force:' not in workflow
