"""Зіставлення заморожених пропозицій у тіньовому пілоті."""

import json
import sys
from fractions import Fraction

from ops.quote_pilot import (
    PilotInputError, _bool, _int, _list, _object, _reject_constant, _scope,
    _text, _time, _unique, _unique_keys, _SCOPE,
)

_BATCH_SIZE = 30
_OFFER = ("price_total_kop", "price_net_kop", "cost_total_kop", "bottleneck_minutes", "preparation_seconds")


def _offer(raw, path):
    offer = _object(raw, path, (*_SCOPE, "frozen_at", "evidence_ref", *_OFFER))
    _text(offer["evidence_ref"], f"{path}.evidence_ref")
    total, net, cost, minutes, seconds = (
        _int(offer[key], f"{path}.{key}", minimum=1 if key in _OFFER[:4] else 0)
        for key in _OFFER
    )
    if total < net or net < cost:
        raise PilotInputError(f"{path}: суми пропозиції суперечать одна одній")
    return _scope(offer, path), _time(offer["frozen_at"], f"{path}.frozen_at"), (
        total, net - cost, minutes, seconds,
    )


def _median_doubled(values):
    values = sorted(values)
    center = len(values) // 2
    return values[center] + values[(len(values) - 1) // 2]


def _decimal_half(doubled):
    whole, half = divmod(abs(doubled), 2)
    return f"{'-' if doubled < 0 else ''}{whole}{'.5' if half else ''}"


def review(payload):
    """Оцінити перші 30 послідовних записів одного протоколу."""
    payload = _object(payload, "review", ("as_of", "protocol_ref", "requests"))
    as_of = _time(payload["as_of"], "review.as_of")
    protocol = _text(payload["protocol_ref"], "review.protocol_ref")
    requests = _list(payload["requests"], "review.requests")
    if len(requests) > _BATCH_SIZE:
        raise PilotInputError("review.requests: передайте одну послідовну партію до 30 заявок")

    seen = set()
    last_received = None
    fixed, adaptive, matched_competitor = [], [], []
    reasons = {"unpriced": 0, "unmatched_scope": 0}
    outcomes = dict.fromkeys(("pending", "won", "lost", "withdrawn"), 0)
    on_time, completed = 0, 0
    for index, raw in enumerate(requests):
        path = f"review.requests[{index}]"
        row = _object(raw, path, (
            "sequence", "id", "received_at", "baseline", "adaptive",
            "competitor", "outcome", "delivery_on_time",
        ))
        _unique(row["id"], seen, f"{path}.id")
        if _int(row["sequence"], f"{path}.sequence", minimum=1) != index + 1:
            raise PilotInputError(f"{path}.sequence: порушено послідовність")
        received = _time(row["received_at"], f"{path}.received_at")
        if received > as_of or (last_received is not None and received < last_received):
            raise PilotInputError(f"{path}.received_at: порушено хронологію")
        last_received = received
        outcome = _text(row["outcome"], f"{path}.outcome")
        if outcome not in outcomes:
            raise PilotInputError(f"{path}.outcome: невідомий результат")
        outcomes[outcome] += 1
        if row["delivery_on_time"] is not None:
            if outcome != "won":
                raise PilotInputError(f"{path}.delivery_on_time: потрібне вигране замовлення")
            on_time += _bool(row["delivery_on_time"], f"{path}.delivery_on_time")
            completed += 1

        offers = {
            key: _offer(row[key], f"{path}.{key}")
            for key in ("baseline", "adaptive") if row[key] is not None
        }
        if any(not received <= offer[1] <= as_of for offer in offers.values()):
            raise PilotInputError(f"{path}: час фіксації пропозиції поза межами спостереження")
        competitor = None
        if row["competitor"] is not None:
            external = _object(row["competitor"], f"{path}.competitor", (
                *_SCOPE, "price_total_kop", "evidence_ref",
            ))
            _text(external["evidence_ref"], f"{path}.competitor.evidence_ref")
            competitor = (
                _scope(external, f"{path}.competitor"),
                _int(external["price_total_kop"], f"{path}.competitor.price_total_kop", minimum=1),
            )

        if len(offers) != 2:
            reasons["unpriced"] += 1
            continue
        old, new = offers["baseline"], offers["adaptive"]
        if old[0] != new[0]:
            reasons["unmatched_scope"] += 1
            continue
        fixed.append(old[2])
        adaptive.append(new[2])
        if competitor is not None and competitor[0] == new[0]:
            matched_competitor.append(competitor[1] - new[2][0])

    report = {
        "protocol_ref": protocol, "status": "collecting", "requests": len(requests),
        "paired": len(fixed), "unpaired": reasons, "observed_outcomes": outcomes,
        "observed_delivery": {"on_time": on_time, "completed_with_evidence": completed},
        "matched_competitor": {
            "count": len(matched_competitor),
            "adaptive_cheaper": sum(delta > 0 for delta in matched_competitor),
        },
        "pairs": None,
    }
    if fixed:
        savings = _median_doubled(old[0] - new[0] for old, new in zip(fixed, adaptive))
        preparation = _median_doubled(old[3] - new[3] for old, new in zip(fixed, adaptive))
        old_rate, new_rate = (
            Fraction(60 * sum(offer[1] for offer in offers), sum(offer[2] for offer in offers))
            for offers in (fixed, adaptive)
        )
        report["pairs"] = {
            "customer_savings_median_kop": _decimal_half(savings),
            "preparation_savings_median_seconds": _decimal_half(preparation),
            "baseline_contribution_kop_per_hour": round(old_rate),
            "adaptive_contribution_kop_per_hour": round(new_rate),
        }
    if len(requests) == _BATCH_SIZE:
        report["status"] = "insufficient_comparable" if len(fixed) < _BATCH_SIZE else "shadow_rejected"
        if len(fixed) == _BATCH_SIZE and savings > 0 and preparation >= 0 and new_rate >= old_rate:
            report["status"] = "review_required"
    return report


def main():
    try:
        payload = json.load(sys.stdin, object_pairs_hook=_unique_keys, parse_constant=_reject_constant)
        result = review(payload)
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
