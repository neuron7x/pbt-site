"""Static tests for exact-head real-media diagnostic workflow."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
YML=ROOT/'.github/workflows/artifact-fit-trial.yml'

def test_pr_head_only_no_write_privileges():
    src=YML.read_text(encoding='utf-8')
    assert "pull_request:" in src and "branches: [main]" in src
    assert "contents: read" in src and "contents: write" not in src
    assert "persist-credentials: false" in src
    assert "github.event.pull_request.head.sha" in src
    assert "test \"$(git rev-parse HEAD)\" = \"$PBT_HEAD_SHA\"" in src
    assert "git push" not in src
    assert "workflow_dispatch:" not in src

def test_hard_cap_enforced_never_fabricates_approval():
    src=YML.read_text(encoding='utf-8')
    assert "64*1024*1024" in src
    assert "'NOT_GRANTED'" in src
    assert "Multifile artifact exceeds" in src
    assert "test \"$result\" -eq 0" in src
    assert "tests/test_reproducibility.py" in src

def test_red_result_keeps_byte_and_codec_evidence():
    src=YML.read_text(encoding='utf-8')
    assert src.count("if: always()")==1
    assert "artifacts/video-fit/" in src
    assert "dist/artifact-budget-preflight.json" in src
    assert "dist/artifact-budget.json" in src
    assert "if-no-files-found: warn" in src


def test_real_media_trial_verifies_the_tracked_inventory_by_digest():
    src = YML.read_text(encoding='utf-8')
    assert "['git','ls-files','-z','--','web/media']" in src
    assert "hashlib.file_digest(handle,'sha256')" in src
    assert "assert built==inventory" in src
