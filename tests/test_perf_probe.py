"""Unit proof for the numerical methodology of the synthetic mobile probe."""
import pytest

from tools.perf_probe import cls_max_session, p75


def test_p75_is_nearest_rank_not_interpolated():
    assert p75([200, 100, 300]) == 300
    assert p75([10, 20, 30, 40]) == 30


@pytest.mark.parametrize("values", [[], [1, 2], [-1, 2, 3],
                                    [1, 2, float("nan")],
                                    [1, 2, float("inf")]])
def test_p75_rejects_invalid_or_insufficient_evidence(values):
    with pytest.raises(ValueError):
        p75(values)


def test_cls_uses_session_windows_and_excludes_recent_input():
    entries = [
        {"start": 100, "value": 0.02, "hadRecentInput": False},
        {"start": 500, "value": 0.03, "hadRecentInput": False},
        {"start": 700, "value": 0.25, "hadRecentInput": True},
        {"start": 2500, "value": 0.04, "hadRecentInput": False},
        {"start": 3400, "value": 0.02, "hadRecentInput": False},
    ]
    assert cls_max_session(entries) == pytest.approx(0.06)


def test_cls_resets_if_a_session_exceeds_five_seconds():
    entries = [{"start": i * 900, "value": 0.02, "hadRecentInput": False}
               for i in range(7)]
    assert cls_max_session(entries) == pytest.approx(0.12)


def test_only_input_related_shifts_do_not_contribute_to_standard_cls():
    assert cls_max_session([{"start": 250, "value": 0.8,
                             "hadRecentInput": True}]) == 0.0
