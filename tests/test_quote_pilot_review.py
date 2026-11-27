import pytest

from ops.quote_pilot_review import PilotInputError, review


def batch(count=30):
    now = "2026-11-27T10:00:00+02:00"
    rows = []
    for n in range(1, count + 1):
        scope = {"scope_id": f"work-{n}", "cohort": "synthetic", "unit": "h", "quantity_milli": 5000}
        baseline = dict(
            scope, frozen_at=now, evidence_ref=f"ordinary-{n}", price_total_kop=120000,
            price_net_kop=100000, cost_total_kop=70000, bottleneck_minutes=120, preparation_seconds=300,
        )
        adaptive = dict(
            baseline, evidence_ref=f"alternative-{n}", price_total_kop=108000,
            price_net_kop=90000, cost_total_kop=60000, bottleneck_minutes=100, preparation_seconds=240,
        )
        rows.append(dict(
            sequence=n, id=f"job-{n}", received_at=now, baseline=baseline, adaptive=adaptive,
            competitor=None, outcome="pending", delivery_on_time=None,
        ))
    return {"as_of": now, "protocol_ref": "synth-protocol", "requests": rows}


def test_review_requires_thirty_consecutive_pairs_before_recommending():
    assert review(batch(29))["status"] == "collecting"
    result = review(batch())
    assert result["status"] == "review_required"
    assert result["requests"] == result["paired"] == 30
    assert result["pairs"] == {
        "customer_savings_median_kop": "12000",
        "preparation_savings_median_seconds": "60",
        "baseline_contribution_kop_per_hour": 15000,
        "adaptive_contribution_kop_per_hour": 18000,
    }


@pytest.mark.parametrize("field,value", [
    ("price_total_kop", 120000), ("cost_total_kop", 65100),
    ("preparation_seconds", 301),
])
def test_review_rejects_price_time_or_contribution_regression(field, value):
    data = batch()
    for row in data["requests"]:
        row["adaptive"][field] = value
    assert review(data)["status"] == "shadow_rejected"


def test_review_preserves_unpriced_and_unmatched_rows_in_denominator():
    data = batch()
    data["requests"][0]["adaptive"] = None
    data["requests"][1]["adaptive"]["quantity_milli"] = 6000
    result = review(data)
    assert result["status"] == "insufficient_comparable"
    assert (result["requests"], result["paired"]) == (30, 28)
    assert result["unpaired"] == {"unpriced": 1, "unmatched_scope": 1}


def test_review_reports_matching_external_quotes_and_actual_outcomes():
    data = batch(2)
    first, second = data["requests"]
    for row in (first, second):
        comparable = {key: row["adaptive"][key] for key in ("scope_id", "cohort", "unit", "quantity_milli")}
        row["competitor"] = dict(comparable, price_total_kop=109000, evidence_ref="synthetic-external")
    second["competitor"]["unit"] = "shift"
    first.update(outcome="won", delivery_on_time=False)
    second["outcome"] = "lost"
    result = review(data)
    assert result["matched_competitor"] == {"count": 1, "adaptive_cheaper": 1}
    assert result["observed_delivery"] == {"on_time": 0, "completed_with_evidence": 1}
    assert result["observed_outcomes"] == {"pending": 0, "won": 1, "lost": 1, "withdrawn": 0}


@pytest.mark.parametrize("field,value", [
    ("sequence", 3), ("id", "job-1"), ("received_at", "2026-11-28T10:00:00+02:00"),
    ("outcome", "unknown"), ("delivery_on_time", False),
])
def test_review_rejects_invalid_intake_and_evidence_sequences(field, value):
    data = batch(2)
    data["requests"][1][field] = value
    with pytest.raises(PilotInputError, match=field):
        review(data)


def test_review_rejects_frozen_offers_outside_the_case_timeline():
    data = batch(1)
    data["requests"][0]["adaptive"]["frozen_at"] = "2026-11-26T10:00:00+02:00"
    with pytest.raises(PilotInputError, match="час фіксації"):
        review(data)


def test_review_preserves_half_kopeck_without_binary_rounding():
    data = batch(2)
    for n, row in enumerate(data["requests"]):
        row["baseline"]["price_total_kop"] = 10**32 + n
    assert review(data)["pairs"]["customer_savings_median_kop"] == f"{10**32 - 108000}.5"
