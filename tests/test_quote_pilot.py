"""Перевірки внутрішньої моделі пропозицій PLAINBUD."""

import json
import subprocess
import sys

import pytest

from ops.quote_pilot import PilotInputError, calibrate, quote


SCOPE = {"scope_id": "scope-1", "cohort": "lift-1", "unit": "hour", "quantity_milli": 1000}


def _date(day, hour=10):
    return f"2026-11-{day:02d}T{hour:02d}:00:00+02:00"


def _option(identifier, day=11, cost=100, price=150, **changes):
    return {
        **SCOPE,
        "id": identifier,
        "start": _date(day),
        "finish": _date(day, 11),
        "feasible": True,
        "capacity_confirmed": True,
        "confirmation_ref": "dispatch-1",
        "confirmed_at": _date(10, 8),
        "valid_until": _date(11, 8),
        "bottleneck_minutes": 60,
        "price_net_kop": price,
        "cost_kop": {"work": cost, "dispatch": 0, "idle": 0, "materials": 0, "other": 0, "risk": 0},
        **changes,
    }


def _job(*options, flexible=True, margin_bps=2000):
    return {
        "as_of": _date(10),
        "job": {**SCOPE, "earliest_start": _date(11), "latest_finish": _date(20), "flexible": flexible},
        "policy": {"minimum_margin_bps": margin_bps, "vat_bps": 2000},
        "options": list(options),
    }


def test_quote_selects_early_slot_and_only_funded_discount():
    early = _option("early")
    flexible = _option("valid-saving", day=13, cost=80, price=130, saving_reason="routing")
    subsidy = _option("unfunded-discount", day=12, cost=79, price=110, saving_reason="routing")
    undocumented = _option("no-reason", day=12, cost=65, price=120)
    later = _option("more-expensive", day=14, cost=92, price=142, saving_reason="idle")
    result = quote(_job(undocumented, later, flexible, subsidy, early))
    assert result["status"] == "review_required"
    assert result["earliest"]["id"] == "early"
    assert result["flexible"]["id"] == "valid-saving"
    assert result["flexible_reason"] == "routing"
    assert result["scope"] == SCOPE
    assert result["earliest"]["bottleneck_minutes"] == result["flexible"]["bottleneck_minutes"] == 60
    assert result["flexible"]["price_net_kop"] == 130
    assert result["flexible"]["price_gross_kop"] == 156
    assert result["earliest"]["contribution_kop"] == result["flexible"]["contribution_kop"] == 50


def test_unfunded_and_undocumented_discounts_produce_only_earliest_option():
    early = _option("early")
    subsidy = _option("unfunded-discount", day=12, cost=79, price=110, saving_reason="routing")
    undocumented = _option("no-reason", day=12, cost=65, price=120)
    result = quote(_job(subsidy, undocumented, early))
    assert result["flexible"] is None
    assert result["flexible_reason"] == "no_verified_savings"


def test_fixed_window_rejects_flexible_proposal_even_when_funded():
    early = _option("early")
    cheaper = _option("later", day=12, cost=80, price=130, saving_reason="routing")
    result = quote(_job(cheaper, early, flexible=False))
    assert result["earliest"]["id"] == "early"
    assert result["flexible"] is None
    assert result["flexible_reason"] == "fixed_window"


@pytest.mark.parametrize(("changes", "expected"), [
    ({"scope_id": "scope-other"}, "scope_mismatch"),
    ({"quantity_milli": 999}, "scope_mismatch"),
    ({"unit": "shift"}, "scope_mismatch"),
    ({"cohort": "lift-other"}, "scope_mismatch"),
    ({"feasible": False}, "infeasible"),
    ({"capacity_confirmed": False, "confirmation_ref": None, "confirmed_at": None, "valid_until": None},
     "capacity_unconfirmed"),
    ({"confirmed_at": _date(10, 11)}, "confirmation_not_current"),
    ({"valid_until": _date(10)}, "confirmation_not_current"),
    ({"finish": _date(21)}, "outside_window"),
    ({"finish": _date(11)}, "outside_window"),
    ({"start": _date(10)}, "outside_window"),
    ({"price_net_kop": 124}, "below_margin_floor"),
])
def test_rejects_ineligible_options(changes, expected):
    result = quote(_job(_option("candidate", **changes)))
    assert result["status"] == "no_eligible_options"
    assert result["earliest"] is None
    assert result["flexible"] is None
    assert result["excluded"] == [{"id": "candidate", "reason": expected}]


def test_margin_and_vat_rounding_are_integer_and_enforced_at_boundary():
    result = quote(_job(_option("below", cost=101, price=126), _option("floor", cost=101, price=127)))
    assert result["excluded"] == [{"id": "below", "reason": "below_margin_floor"}]
    selected = result["earliest"]
    assert selected["minimum_net_kop"] == 127
    assert selected["margin_bps"] == 2047
    assert selected["price_gross_kop"] == 152
    payload = _job(_option("half", cost=1, price=5))
    payload["policy"]["vat_bps"] = 1000
    assert quote(payload)["earliest"]["price_gross_kop"] == 6


def test_tie_is_deterministic_across_order_and_timezone_aliases():
    first = _option("a", start="2026-11-11T08:00:00Z", finish="2026-11-11T09:00:00Z")
    second = _option("b")
    forward = quote(_job(first, second))
    reverse = quote(_job(second, first))
    assert forward == reverse
    assert forward["earliest"]["id"] == "a"


@pytest.mark.parametrize("changes", [
    {"cost_kop": {"work": 100}},
    {"price_net_kop": True},
    {"bottleneck_minutes": 0},
    {"confirmation_ref": None},
    {"confirmed_at": "2026-11-10T08:00:00"},
    {"saving_reason": "estimated"},
])
def test_input_errors_invalidate_batch_even_when_it_contains_an_eligible_option(changes):
    with pytest.raises(PilotInputError):
        quote(_job(_option("good"), _option("bad", **changes)))


def test_duplicate_option_id_fails_closed():
    with pytest.raises(PilotInputError, match="ідентифікатор повторюється"):
        quote(_job(_option("duplicate"), _option("duplicate")))


def _observation(identifier, frozen, observed, actual, *, estimate=100, cohort="lift-1"):
    return {
        "id": identifier,
        "cohort": cohort,
        "estimated_minutes": estimate,
        "actual_minutes": actual,
        "estimate_frozen_at": _date(frozen),
        "observed_at": _date(observed),
    }


def _calibration(*observations, maximum=1500):
    return {
        "cohort": "lift-1",
        "cutoff": _date(10),
        "policy": {"min_training": 2, "min_shadow": 2, "max_adjustment_bps": maximum},
        "observations": list(observations),
    }


def test_calibration_uses_only_comparable_chronological_records_and_clamps():
    payload = _calibration(
        _observation("shadow-b", 11, 12, 114),
        _observation("train-a", 5, 6, 140),
        _observation("other", 5, 6, 300, cohort="lift-other"),
        _observation("embargoed", 9, 10, 1),
        _observation("shadow-a", 10, 11, 119),
        _observation("train-b", 7, 9, 130),
    )
    result = calibrate(payload)
    assert result == {
        "status": "review_required",
        "training_count": 2,
        "shadow_count": 2,
        "embargoed_count": 1,
        "other_cohort_count": 1,
        "tested_adjustment_bps": 1500,
        "recommended_adjustment_bps": 1500,
        "baseline_shadow": {"total_abs_minutes": 33, "max_abs_minutes": 19},
        "adjusted_shadow": {"total_abs_minutes": 5, "max_abs_minutes": 4},
    }
    payload["observations"].reverse()
    assert calibrate(payload) == result


def test_shadow_rejects_adjustment_if_worst_error_grows_despite_total_improving():
    result = calibrate(_calibration(
        _observation("train-a", 5, 6, 129),
        _observation("train-b", 7, 9, 130),
        _observation("shadow-a", 10, 11, 119),
        _observation("shadow-b", 11, 12, 118),
        _observation("shadow-c", 12, 13, 95),
    ))
    assert result["status"] == "shadow_rejected"
    assert result["baseline_shadow"] == {"total_abs_minutes": 42, "max_abs_minutes": 19}
    assert result["adjusted_shadow"] == {"total_abs_minutes": 27, "max_abs_minutes": 20}
    assert result["recommended_adjustment_bps"] is None


def test_insufficient_independent_shadow_data_does_not_emit_adjustment():
    result = calibrate(_calibration(
        _observation("train-a", 5, 6, 145),
        _observation("train-b", 7, 9, 145),
        _observation("embargoed", 9, 11, 145),
        _observation("shadow-a", 10, 11, 145),
    ))
    assert result["status"] == "insufficient_data"
    assert result["tested_adjustment_bps"] is None
    assert result["recommended_adjustment_bps"] is None


def test_calibration_rejects_duplicate_ids_and_post_outcome_estimates():
    observation = _observation("record", 5, 6, 120)
    with pytest.raises(PilotInputError, match="ідентифікатор повторюється"):
        calibrate(_calibration(observation, observation))
    with pytest.raises(PilotInputError, match="оцінку слід зафіксувати"):
        calibrate(_calibration(_observation("leak", 7, 6, 120)))


@pytest.mark.parametrize("raw", ['{"duplicate": 1, "duplicate": 2}', '{"n": NaN}', "{"])
def test_cli_fails_closed_with_json_error(raw):
    run = subprocess.run(
        [sys.executable, "-m", "ops.quote_pilot", "quote"],
        input=raw, capture_output=True, encoding="utf-8", check=False,
    )
    assert run.returncode == 2
    assert set(json.loads(run.stdout)) == {"error"}
    assert not run.stderr


@pytest.mark.parametrize(("mode", "payload", "expected_status"), [
    ("quote", _job(_option("good")), "review_required"),
    ("calibrate", _calibration(), "insufficient_data"),
])
def test_cli_uses_stdin_and_emits_json(mode, payload, expected_status):
    run = subprocess.run(
        [sys.executable, "-m", "ops.quote_pilot", mode],
        input=json.dumps(payload), capture_output=True, encoding="utf-8", check=False,
    )
    assert run.returncode == 0
    assert json.loads(run.stdout)["status"] == expected_status
    assert not run.stderr
