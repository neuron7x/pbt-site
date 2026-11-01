"""OPS-03: a missed heartbeat is not an outage, and neither is a lost lead."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('incident_correlate', ROOT / 'ops/incident_correlate.py')
ic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ic)
DOWN = {'provider_event_id': 'mon-1', 'state': 'DOWN'}


def test_intentional_power_guard_stop_is_not_an_application_outage():
    r = ic.classify({'monitor_event': DOWN, 'power_guard_marker': True, 'health': {'answered': False, 'ok': False}})
    assert r['root_cause'] == 'INTENTIONAL_POWER_GUARD_STOP' and r['lead_loss'] == 'UNKNOWN'


def test_monitor_down_with_site_answering_locally_blames_the_path():
    r = ic.classify({'monitor_event': DOWN, 'power_guard_marker': False, 'health': {'answered': True, 'ok': True}})
    assert r['root_cause'] == 'MONITOR_OR_PATH_FAILURE_SITE_ANSWERED_LOCALLY' and r['site_state'] == 'UP'


def test_aggregate_missed_heartbeats_without_provider_identity_stay_unknown():
    r = ic.classify({'monitor_event': {'state': 'DOWN'}, 'power_guard_marker': False, 'health': {'answered': False, 'ok': False}})
    assert r['root_cause'] == 'UNKNOWN' and r['reason'] == 'monitor_event_without_provider_identity'


def test_unobserved_local_state_never_becomes_a_cause():
    r = ic.classify({'monitor_event': DOWN})
    assert r['root_cause'] == 'UNKNOWN' and r['lead_loss'] == 'UNKNOWN' and r['site_state'] == 'UNKNOWN'


def test_lead_loss_needs_receiver_evidence_in_both_directions():
    clean = {'storage_snapshot': 'PASS', 'receiver_persistence': 'UNKNOWN'}
    assert ic.classify({'monitor_event': DOWN, 'readiness': {'signals': clean}})['lead_loss'] == 'UNKNOWN'
    good = {'storage_snapshot': 'PASS', 'receiver_persistence': 'PASS'}
    assert ic.classify({'monitor_event': DOWN, 'readiness': {'signals': good}})['lead_loss'] == 'NOT_OBSERVED'
    gap = {'storage_snapshot': 'PASS', 'receiver_persistence': 'FAIL'}
    assert ic.classify({'monitor_event': DOWN, 'readiness': {'signals': gap}})['lead_loss'] == 'SUSPECTED'


def test_delivery_degradation_is_reported_separately_from_cause():
    signals = {'storage_snapshot': 'PASS', 'delivery_backlog': 'FAIL'}
    r = ic.classify({'monitor_event': {'provider_event_id': 'm', 'state': 'UP'}, 'readiness': {'signals': signals}})
    assert r['delivery'] == 'DEGRADED' and r['root_cause'] == 'UNKNOWN'
