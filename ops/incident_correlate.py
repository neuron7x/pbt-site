#!/usr/bin/env python3
"""Classify a monitor alert against local evidence. Unknown stays unknown; no outage is invented.

Input JSON (aggregates only, never lead data):
  monitor_event: {provider_event_id, state: DOWN|UP}          external monitor
  power_guard_marker: true|false|null                          ~/.local/state/pbt-power-guard/stopped.json
  health: {answered: bool, ok: bool}|null                      ops/health.py at the same moment
  readiness: {signals: {...}}|null                             ops/readiness.py output

A monitor proves only that a monitor saw something. Lead loss is never inferred from it: accepted
leads are checked against storage, and without a receiver receipt loss downstream stays UNKNOWN.
"""
import argparse
import json
from pathlib import Path
import sys


def classify(event):
    monitor = event.get('monitor_event') or {}
    event_id = monitor.get('provider_event_id')
    state = monitor.get('state')
    marker = event.get('power_guard_marker')
    health = event.get('health')
    signals = (event.get('readiness') or {}).get('signals') or {}
    out = {'provider_event_id': event_id, 'root_cause': 'UNKNOWN', 'lead_loss': 'UNKNOWN',
           'site_state': 'UNKNOWN', 'evidence_scope': 'correlation_of_supplied_signals_not_a_measurement'}
    if not event_id or state not in ('DOWN', 'UP'):
        out['reason'] = 'monitor_event_without_provider_identity'
        return out
    if health is not None:
        out['site_state'] = 'UP' if health.get('answered') and health.get('ok') else 'DOWN'
    storage = signals.get('storage_snapshot')
    if storage == 'PASS' and signals.get('receiver_persistence') == 'PASS':
        out['lead_loss'] = 'NOT_OBSERVED'
    elif storage == 'FAIL' or signals.get('receiver_persistence') == 'FAIL':
        out['lead_loss'] = 'SUSPECTED'
    if state == 'DOWN':
        if marker is True:
            out['root_cause'] = 'INTENTIONAL_POWER_GUARD_STOP'
        elif marker is False and out['site_state'] == 'DOWN':
            out['root_cause'] = 'SITE_DOWN_CAUSE_NOT_ESTABLISHED'
        elif marker is False and out['site_state'] == 'UP':
            out['root_cause'] = 'MONITOR_OR_PATH_FAILURE_SITE_ANSWERED_LOCALLY'
    if signals.get('delivery_backlog') == 'FAIL' or signals.get('delivery_terminal_failures') == 'FAIL':
        out['delivery'] = 'DEGRADED'
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('event', type=Path)
    a = p.parse_args(argv)
    try:
        event = json.loads(a.event.read_text(encoding='utf-8'))
        if not isinstance(event, dict):
            raise ValueError('not_an_object')
    except (OSError, ValueError) as exc:
        print(json.dumps({'root_cause': 'UNKNOWN', 'lead_loss': 'UNKNOWN', 'reason': type(exc).__name__}))
        return 2
    result = classify(event)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['root_cause'] != 'UNKNOWN' else 2


if __name__ == '__main__':
    sys.exit(main())
