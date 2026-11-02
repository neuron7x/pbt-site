"""Fail-closed required evidence-role triggers across PR, exact-main and dispatch.

The evidence policy requires all five workflows for every source revision.
Path filters on required roles suppress GitHub Actions entirely for some diffs,
so a docs-only or tools-only change must not make an unconditional role vanish.
This tests workflow configuration, not the existence of completed CI receipts.
"""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1] / ".github" / "workflows"
MAIN_GATES = ("pr-quality.yml", "runtime-hardening.yml",
              "visual-evidence.yml", "security-assurance.yml",
              "runtime-soak.yml")
EVENTS_REQUIRED = ("pull_request", "push")
EVENT_FILTER = re.compile(
    r"(?m)^    (?:paths|paths-ignore|branches-ignore|tags|tags-ignore):"
)


def _events(name, source=None):
    if source is None:
        source = (ROOT / name).read_text(encoding="utf-8")
    assert "\non:\n" in source, name
    assert "\npermissions:\n" in source, name
    return source.split("\non:\n", 1)[1].split("\npermissions:\n", 1)[0]


def _event(events, event):
    match = re.search(
        r"(?ms)^  " + re.escape(event) + r":\n(.*?)(?=^  [a-z][a-z_]*:|\Z)",
        events,
    )
    assert match is not None, f"missing event: {event}"
    return match.group(1)


def _assert_unfiltered_required_roles(name, source=None):
    events = _events(name, source)
    assert "  workflow_dispatch:\n" in events, name
    for event in EVENTS_REQUIRED:
        block = _event(events, event)
        assert re.search(r"(?m)^    branches: \[main\]$", block), (name, event)
        assert not EVENT_FILTER.search(block), (
            f"{name} {event} suppresses mandatory evidence for some revisions"
        )


@pytest.mark.parametrize("name", MAIN_GATES)
def test_every_required_role_can_run_on_every_pr_and_main_push(name):
    _assert_unfiltered_required_roles(name)


@pytest.mark.parametrize("name", MAIN_GATES)
@pytest.mark.parametrize("event", EVENTS_REQUIRED)
@pytest.mark.parametrize("filter_key", ("paths", "paths-ignore"))
def test_required_role_path_filter_mutant_is_rejected(name, event, filter_key):
    source = (ROOT / name).read_text(encoding="utf-8")
    anchor = f"  {event}:\n    branches: [main]\n"
    assert anchor in source, (name, event)
    mutant = source.replace(anchor, anchor + f"    {filter_key}:\n      - 'server/**'\n", 1)
    assert mutant != source
    with pytest.raises(AssertionError):
        _assert_unfiltered_required_roles(name, mutant)


def test_push_jobs_checkout_the_actual_merged_sha():
    for name in MAIN_GATES:
        source = (ROOT / name).read_text(encoding="utf-8")
        assert "PBT_HEAD_SHA: ${{ github.event.pull_request.head.sha || github.sha }}" in source, name
        assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in source, name
