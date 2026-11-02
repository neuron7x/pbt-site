"""Fail-closed verification: a merged main SHA must trigger real CI, not reuse PR evidence.

These checks guard the event configuration (including the soak's path selection).
They do not fabricate post-merge CI receipts or claim workflow completion.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / ".github" / "workflows"
MAIN_GATES = ("pr-quality.yml", "runtime-hardening.yml",
              "visual-evidence.yml", "security-assurance.yml",
              "runtime-soak.yml")
SOURCE_PATTERNS = {
    "server/**", "ops/**", "web/**", "tools/**", "tests/**",
    "config/**", "assurance/**", "Makefile", "requirements*.txt",
    ".github/workflows/**",
}


def _events(name):
    source = (ROOT / name).read_text(encoding="utf-8")
    assert "\non:\n" in source, name
    assert "\npermissions:\n" in source, name
    return source.split("\non:\n", 1)[1].split("\npermissions:\n", 1)[0]


def _event(events, event):
    match = re.search(r"(?ms)^  " + re.escape(event) + r":\n(.*?)(?=^  [a-z][a-z_]*:|\Z)", events)
    assert match is not None, f"missing event: {event}"
    return match.group(1)


def test_main_push_executes_all_five_evidence_workflows():
    for name in MAIN_GATES:
        events = _events(name)
        assert "  pull_request:\n" in events, name
        assert "  workflow_dispatch:\n" in events, name
        push = _event(events, "push")
        assert re.search(r"(?m)^    branches: \[main\]$", push), name


def test_runtime_soak_covers_source_and_assurance_mutations_both_events():
    events = _events("runtime-soak.yml")
    for event in ("pull_request", "push"):
        block = _event(events, event)
        patterns = set(re.findall(r"(?m)^      - '([^']+)'$", block))
        assert SOURCE_PATTERNS <= patterns, (
            f"{event} cannot produce exact-source soak for {SOURCE_PATTERNS - patterns}")


def test_push_jobs_checkout_the_actual_merged_sha():
    for name in MAIN_GATES:
        source = (ROOT / name).read_text(encoding="utf-8")
        assert "PBT_HEAD_SHA: ${{ github.event.pull_request.head.sha || github.sha }}" in source, name
        assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in source, name
