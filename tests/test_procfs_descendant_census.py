"""Child-process evidence must work on both Linux procfs variants.

Synthetic /proc fixtures assert real descendant identity, including grandchildren,
and enforce an explicit failure when neither observation interface is available.
No test is skipped or treated as a successful zero-child sample.
"""
from pathlib import Path

import pytest

from tools.runtime_soak import _descendants


def _proc(root, pid, parent, *, children=None, tid=None):
    task = root / str(pid) / "task" / str(tid or pid)
    task.mkdir(parents=True)
    (root / str(pid) / "status").write_text(
        f"Name:\tfixture\nState:\tS (sleeping)\nPPid:\t{parent}\n"
    )
    if children is not None:
        (task / "children").write_text(children)


def test_task_children_interface_enumerates_worker_threads_and_grandchildren(tmp_path):
    _proc(tmp_path, 100, 1, children="", tid=100)
    worker = tmp_path / "100" / "task" / "101"
    worker.mkdir()
    (worker / "children").write_text("200")
    _proc(tmp_path, 200, 100, children="300")
    _proc(tmp_path, 300, 200, children="")
    _proc(tmp_path, 900, 1, children="")
    assert _descendants(100, proc_root=tmp_path) == {200, 300}


def test_missing_all_children_files_falls_back_to_process_ppid(tmp_path):
    _proc(tmp_path, 300, 200)
    _proc(tmp_path, 900, 1)
    _proc(tmp_path, 100, 1)
    _proc(tmp_path, 200, 100)
    assert _descendants(100, proc_root=tmp_path) == {200, 300}


def test_fallback_zero_children_requires_observable_root(tmp_path):
    _proc(tmp_path, 100, 1)
    _proc(tmp_path, 900, 1)
    assert _descendants(100, proc_root=tmp_path) == set()


def test_missing_both_interfaces_rejects_instead_of_certifying_zero(tmp_path):
    _proc(tmp_path, 900, 1)
    with pytest.raises(RuntimeError, match="proc_root_not_observed"):
        _descendants(100, proc_root=tmp_path)


def test_corrupted_ppid_fails_closed(tmp_path):
    _proc(tmp_path, 100, 1)
    (tmp_path / "100" / "status").write_text("State:\tS (sleeping)\n")
    with pytest.raises(RuntimeError, match="proc_ppid_missing"):
        _descendants(100, proc_root=tmp_path)


def test_missing_worker_children_cannot_certify_empty_tree(tmp_path):
    _proc(tmp_path, 100, 1, children="")
    (tmp_path / "100" / "task" / "101").mkdir()
    _proc(tmp_path, 200, 100)
    _proc(tmp_path, 300, 200)
    assert _descendants(100, proc_root=tmp_path) == {200, 300}


def test_missing_descendant_children_cannot_hide_grandchild(tmp_path):
    _proc(tmp_path, 100, 1, children="200")
    _proc(tmp_path, 200, 100)
    _proc(tmp_path, 300, 200)
    assert _descendants(100, proc_root=tmp_path) == {200, 300}


@pytest.mark.parametrize("missing_task_directory", [False, True])
def test_unobservable_descendant_task_directory_uses_ppid(tmp_path, missing_task_directory):
    _proc(tmp_path, 100, 1, children="200")
    _proc(tmp_path, 200, 100)
    _proc(tmp_path, 300, 200)
    (tmp_path / "200" / "task" / "200").rmdir()
    if missing_task_directory:
        (tmp_path / "200" / "task").rmdir()
    assert _descendants(100, proc_root=tmp_path) == {200, 300}


def test_unreadable_children_interface_uses_independent_status(tmp_path, monkeypatch):
    _proc(tmp_path, 100, 1, children="200")
    _proc(tmp_path, 200, 100)
    original = Path.read_text

    def read_text(path, *args, **kwargs):
        if path.name == "children":
            raise PermissionError("fixture children interface denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    assert _descendants(100, proc_root=tmp_path) == {200}


def test_missing_status_of_existing_process_cannot_certify_empty_tree(tmp_path):
    _proc(tmp_path, 100, 1)
    _proc(tmp_path, 200, 100)
    (tmp_path / "200" / "status").unlink()
    with pytest.raises(RuntimeError, match="proc_status_unavailable"):
        _descendants(100, proc_root=tmp_path)


@pytest.mark.parametrize("children", ["0", "-200", "+200", "2\u0660\u0660"])
def test_invalid_child_pid_is_not_resource_evidence(tmp_path, children):
    _proc(tmp_path, 100, 1, children=children)
    with pytest.raises(RuntimeError, match="proc_child_pid_invalid"):
        _descendants(100, proc_root=tmp_path)


def test_repeated_child_pid_is_counted_once(tmp_path):
    _proc(tmp_path, 100, 1, children="200 200")
    _proc(tmp_path, 200, 100, children="")
    assert _descendants(100, proc_root=tmp_path) == {200}


def test_unreadable_status_fails_closed(tmp_path, monkeypatch):
    _proc(tmp_path, 100, 1)
    _proc(tmp_path, 200, 100)
    original = Path.read_text

    def read_text(path, *args, **kwargs):
        if path == tmp_path / "200" / "status":
            raise PermissionError("fixture status denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    with pytest.raises(RuntimeError, match="proc_descendant_census_unavailable"):
        _descendants(100, proc_root=tmp_path)


def test_process_exiting_during_status_scan_is_not_an_observation_failure(tmp_path, monkeypatch):
    _proc(tmp_path, 100, 1)
    vanished = tmp_path / "200"
    vanished.mkdir()
    original = Path.read_text

    def read_text(path, *args, **kwargs):
        if path == vanished / "status":
            vanished.rmdir()
            raise FileNotFoundError("fixture process exited")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    assert _descendants(100, proc_root=tmp_path) == set()
