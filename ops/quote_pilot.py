"""Підготовка внутрішніх пропозицій і тіньова перевірка оцінок."""

import argparse
import json
import sys
from datetime import datetime, timezone
from fractions import Fraction
from statistics import median

_BPS = 10_000
_SCOPE = ("scope_id", "cohort", "unit", "quantity_milli")
_COSTS = ("work", "dispatch", "idle", "materials", "other", "risk")
_SAVINGS = ("routing", "idle", "machine", "capacity")


class PilotInputError(ValueError):
    """Дані не відповідають контракту пілота."""


def _object(value, path, required, optional=()):
    if not isinstance(value, dict):
        raise PilotInputError(f"{path}: очікується об'єкт")
    for key in required:
        if key not in value:
            raise PilotInputError(f"{path}.{key}: обов'язкове поле")
    if set(value).difference(required, optional):
        raise PilotInputError(f"{path}: невідоме поле")
    return value


def _list(value, path):
    if not isinstance(value, list):
        raise PilotInputError(f"{path}: очікується масив")
    return value


def _text(value, path):
    if not isinstance(value, str) or not value or value.strip() != value:
        raise PilotInputError(f"{path}: очікується непорожній рядок без крайніх пробілів")
    return value


def _int(value, path, minimum=0, maximum=None):
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise PilotInputError(f"{path}: ціле число поза допустимими межами")
    return value


def _bool(value, path):
    if type(value) is not bool:
        raise PilotInputError(f"{path}: очікується логічне значення")
    return value


def _time(value, path):
    value = _text(value, path)
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.utcoffset() is not None:
            return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        pass
    raise PilotInputError(f"{path}: очікується ISO дата й час із часовим поясом")


def _scope(value, path):
    return (
        _text(value["scope_id"], f"{path}.scope_id"),
        _text(value["cohort"], f"{path}.cohort"),
        _text(value["unit"], f"{path}.unit"),
        _int(value["quantity_milli"], f"{path}.quantity_milli", minimum=1),
    )


def _unique(value, seen, path):
    identifier = _text(value, path)
    if identifier in seen:
        raise PilotInputError(f"{path}: ідентифікатор повторюється")
    seen.add(identifier)
    return identifier


def _round_half_up(numerator, denominator):
    return (2 * numerator + denominator) // (2 * denominator)


def _option(raw, path, seen, scope, window, as_of, margin_bps, vat_bps):
    option = _object(
        raw, path,
        ("id", *_SCOPE, "start", "finish", "feasible", "capacity_confirmed",
         "confirmation_ref", "confirmed_at", "valid_until", "bottleneck_minutes",
         "price_net_kop", "cost_kop"),
        ("saving_reason",),
    )
    identifier = _unique(option["id"], seen, f"{path}.id")
    comparable = _scope(option, path) == scope
    start = _time(option["start"], f"{path}.start")
    finish = _time(option["finish"], f"{path}.finish")
    feasible = _bool(option["feasible"], f"{path}.feasible")
    confirmed = _bool(option["capacity_confirmed"], f"{path}.capacity_confirmed")
    start_limit, finish_limit = window
    price = _int(option["price_net_kop"], f"{path}.price_net_kop", minimum=1)
    bottleneck = _int(option["bottleneck_minutes"], f"{path}.bottleneck_minutes", minimum=1)
    costs = _object(option["cost_kop"], f"{path}.cost_kop", _COSTS)
    cost = sum(_int(costs[key], f"{path}.cost_kop.{key}") for key in _COSTS)
    reason = option.get("saving_reason")
    if "saving_reason" in option and reason not in _SAVINGS:
        raise PilotInputError(f"{path}.saving_reason: невідома підстава економії")
    if cost == 0:
        raise PilotInputError(f"{path}.cost_kop: сукупні витрати мають бути додатними")

    confirmation_ref = option["confirmation_ref"]
    confirmed_at = option["confirmed_at"]
    valid_until = option["valid_until"]
    if confirmation_ref is not None or confirmed:
        confirmation_ref = _text(confirmation_ref, f"{path}.confirmation_ref")
    if confirmed_at is not None or confirmed:
        confirmed_at = _time(confirmed_at, f"{path}.confirmed_at")
    if valid_until is not None or confirmed:
        valid_until = _time(valid_until, f"{path}.valid_until")

    floor = (cost * _BPS + (_BPS - margin_bps) - 1) // (_BPS - margin_bps)
    if not comparable:
        excluded = "scope_mismatch"
    elif not feasible:
        excluded = "infeasible"
    elif not confirmed:
        excluded = "capacity_unconfirmed"
    elif not confirmed_at <= as_of < valid_until:
        excluded = "confirmation_not_current"
    elif not start > as_of or not start_limit <= start < finish <= finish_limit:
        excluded = "outside_window"
    elif price < floor:
        excluded = "below_margin_floor"
    else:
        excluded = None

    contribution = price - cost
    return {
        "id": identifier,
        "start": start,
        "finish": finish,
        "confirmation_ref": confirmation_ref,
        "valid_until": valid_until,
        "price_net_kop": price,
        "price_gross_kop": price + _round_half_up(price * vat_bps, _BPS),
        "cost_total_kop": cost,
        "minimum_net_kop": floor,
        "contribution_kop": contribution,
        "margin_bps": contribution * _BPS // price,
        "contribution_per_bottleneck_hour_kop": _round_half_up(contribution * 60, bottleneck),
        "saving_reason": reason,
    }, excluded


def _quote_record(option):
    if option is None:
        return None
    return {
        **option,
        "start": option["start"].isoformat(),
        "finish": option["finish"].isoformat(),
        "valid_until": option["valid_until"].isoformat(),
    }


def quote(payload):
    """Відібрати придатні варіанти для диспетчера."""
    payload = _object(payload, "quote", ("as_of", "policy", "job", "options"))
    as_of = _time(payload["as_of"], "quote.as_of")
    policy = _object(payload["policy"], "quote.policy", ("minimum_margin_bps", "vat_bps"))
    margin_bps = _int(policy["minimum_margin_bps"], "quote.policy.minimum_margin_bps", minimum=1, maximum=9_999)
    vat_bps = _int(policy["vat_bps"], "quote.policy.vat_bps", maximum=_BPS)
    job = _object(payload["job"], "quote.job", (*_SCOPE, "earliest_start", "latest_finish", "flexible"))
    scope = _scope(job, "quote.job")
    start = _time(job["earliest_start"], "quote.job.earliest_start")
    finish = _time(job["latest_finish"], "quote.job.latest_finish")
    flexible_requested = _bool(job["flexible"], "quote.job.flexible")
    if start >= finish:
        raise PilotInputError("quote.job: кінець вікна має бути пізніше початку")

    eligible = []
    excluded = []
    seen = set()
    for index, raw in enumerate(_list(payload["options"], "quote.options")):
        option, reason = _option(
            raw, f"quote.options[{index}]", seen, scope, (start, finish), as_of, margin_bps, vat_bps,
        )
        if reason is None:
            eligible.append(option)
        else:
            excluded.append({"id": option["id"], "reason": reason})
    earliest = min(eligible, key=lambda item: (
        item["start"], item["finish"], item["price_net_kop"], item["id"],
    ), default=None)

    alternatives = []
    if earliest is not None and flexible_requested:
        for option in eligible:
            discount = earliest["price_net_kop"] - option["price_net_kop"]
            savings = earliest["cost_total_kop"] - option["cost_total_kop"]
            if option["saving_reason"] and 0 < discount <= savings:
                alternatives.append(option)
    flexible = min(alternatives, key=lambda item: (
        item["price_net_kop"], item["finish"], item["start"], item["id"],
    ), default=None)
    if not flexible_requested:
        flexible_reason = "fixed_window"
    elif earliest is None:
        flexible_reason = "no_eligible_options"
    elif flexible is None:
        flexible_reason = "no_verified_savings"
    else:
        flexible_reason = flexible["saving_reason"]

    return {
        "status": "review_required" if earliest else "no_eligible_options",
        "earliest": _quote_record(earliest),
        "flexible": _quote_record(flexible),
        "flexible_reason": flexible_reason,
        "excluded": sorted(excluded, key=lambda item: item["id"]),
    }


def calibrate(payload):
    """Перевірити поправку до тривалості на хронологічно відокремлених роботах."""
    payload = _object(payload, "calibrate", ("cohort", "cutoff", "policy", "observations"))
    cohort = _text(payload["cohort"], "calibrate.cohort")
    cutoff = _time(payload["cutoff"], "calibrate.cutoff")
    policy = _object(payload["policy"], "calibrate.policy", ("min_training", "min_shadow", "max_adjustment_bps"))
    min_training = _int(policy["min_training"], "calibrate.policy.min_training", minimum=2)
    min_shadow = _int(policy["min_shadow"], "calibrate.policy.min_shadow", minimum=2)
    max_adjustment = _int(
        policy["max_adjustment_bps"], "calibrate.policy.max_adjustment_bps", maximum=9_999,
    )

    training = []
    shadow = []
    embargoed = 0
    other_cohort = 0
    seen = set()
    for index, raw in enumerate(_list(payload["observations"], "calibrate.observations")):
        path = f"calibrate.observations[{index}]"
        row = _object(
            raw, path, ("id", "cohort", "estimated_minutes", "actual_minutes", "estimate_frozen_at", "observed_at"),
        )
        _unique(row["id"], seen, f"{path}.id")
        comparable = _text(row["cohort"], f"{path}.cohort") == cohort
        estimate = _int(row["estimated_minutes"], f"{path}.estimated_minutes", minimum=1)
        actual = _int(row["actual_minutes"], f"{path}.actual_minutes", minimum=1)
        frozen_at = _time(row["estimate_frozen_at"], f"{path}.estimate_frozen_at")
        observed_at = _time(row["observed_at"], f"{path}.observed_at")
        if frozen_at >= observed_at:
            raise PilotInputError(f"{path}: оцінку слід зафіксувати до спостереження")
        if not comparable:
            other_cohort += 1
        elif observed_at < cutoff:
            training.append(Fraction(actual, estimate))
        elif frozen_at >= cutoff:
            shadow.append((estimate, actual))
        else:
            embargoed += 1

    report = {
        "status": "insufficient_data",
        "training_count": len(training),
        "shadow_count": len(shadow),
        "embargoed_count": embargoed,
        "other_cohort_count": other_cohort,
        "tested_adjustment_bps": None,
        "recommended_adjustment_bps": None,
        "baseline_shadow": None,
        "adjusted_shadow": None,
    }
    if len(training) < min_training or len(shadow) < min_shadow:
        return report

    ratio = median(training) * _BPS
    candidate = _round_half_up(ratio.numerator, ratio.denominator) - _BPS
    adjustment = min(max_adjustment, max(-max_adjustment, candidate))
    baseline = [abs(estimate - actual) for estimate, actual in shadow]
    adjusted = [
        abs(max(1, _round_half_up(estimate * (_BPS + adjustment), _BPS)) - actual)
        for estimate, actual in shadow
    ]
    report.update({
        "status": "shadow_rejected",
        "tested_adjustment_bps": adjustment,
        "baseline_shadow": {"total_abs_minutes": sum(baseline), "max_abs_minutes": max(baseline)},
        "adjusted_shadow": {"total_abs_minutes": sum(adjusted), "max_abs_minutes": max(adjusted)},
    })
    if sum(adjusted) < sum(baseline) and max(adjusted) <= max(baseline):
        report["status"] = "review_required"
        report["recommended_adjustment_bps"] = adjustment
    return report


def _unique_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise PilotInputError("JSON: поле повторюється")
        value[key] = item
    return value


def _reject_constant(_):
    raise PilotInputError("JSON: число має бути скінченним")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("quote", "calibrate"))
    mode = parser.parse_args().mode
    try:
        payload = json.load(sys.stdin, object_pairs_hook=_unique_keys, parse_constant=_reject_constant)
        result = quote(payload) if mode == "quote" else calibrate(payload)
    except PilotInputError as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 2
    except (ValueError, UnicodeError, RecursionError):
        print(json.dumps({"error": "Некоректний JSON"}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
