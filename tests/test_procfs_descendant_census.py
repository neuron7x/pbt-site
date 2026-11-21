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
