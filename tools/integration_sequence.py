#!/usr/bin/env python3
"""Fail-closed static plan for CRM-first, standalone-site-second integration.

This tool never validates signatures, inspects deployment, or grants authority.
A green lint means only that the currently deferred plan is internally sound.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIGNALS = (
    'crm_independent_acceptance', 'website_independent_acceptance',
    'owner_integration_start', 'shared_contract_accepted',
    'staging_e2e_accepted', 'security_privacy_accepted',
    'rollback_verified', 'provider_evidence_accepted',
    'owner_live_activation',
)
LEVELS = frozenset(('UNKNOWN', 'PASS', 'FAIL'))
CHANNELS = ('site_to_crm', 'crm_to_site', 'customer_status')
SOURCE_REFS = {
    'decision': 'https://github.com/neuron7x/pbt-site/issues/38',
    'jira': 'https://neuron7x.atlassian.net/browse/KAN-158',
    'adr': 'docs/ADR-0001-INTEGRATION-SEQUENCE.md',
    'release_hold': 'docs/PRODUCTION_HOLD.md',
}
POLICY_KEYS = frozenset(('schema_version', 'program', 'work_priority',
                         'completion_signals', 'planned_activation',
                         'references', 'evidence_class'))


def unique_json(text: str) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate_key:' + key)
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError('non_json_constant:' + value)

    obj = json.loads(text, object_pairs_hook=unique, parse_constant=invalid_constant)
    if type(obj) is not dict:
        raise ValueError('policy_not_object')
    return obj


def _exact_keys(value, keys, label):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError('invalid_' + label + '_keys')


def validate_frozen_policy(policy: dict) -> dict:
    """v1 is a non-authorizing freeze; promotion needs a separate audited schema."""
    _exact_keys(policy, POLICY_KEYS, 'policy')
    if type(policy['schema_version']) is not int or policy['schema_version'] != 1:
        raise ValueError('unknown_schema_version')
    if policy['program'] != 'PLAINBUD_PBT_CRM':
        raise ValueError('unexpected_program')
    if policy['work_priority'] != 'CRM_FIRST':
        raise ValueError('premature_stage_transition')
    if policy['evidence_class'] != 'PLAN_ONLY_NOT_RUNTIME_ATTESTATION':
        raise ValueError('invalid_evidence_claim')
    _exact_keys(policy['completion_signals'], SIGNALS, 'signals')
    if any(type(value) is not str or value not in LEVELS
           for value in policy['completion_signals'].values()):
        raise ValueError('invalid_signal_type_or_state')
    if any(value != 'UNKNOWN' for value in policy['completion_signals'].values()):
        raise ValueError('unverified_status_promotion')
    _exact_keys(policy['planned_activation'], CHANNELS, 'activation')
    if any(type(value) is not bool or value is not False
           for value in policy['planned_activation'].values()):
        raise ValueError('premature_activation')
    if policy['references'] != SOURCE_REFS:
        raise ValueError('authority_references_changed')
    return {'schema_version': 1, 'policy_consistent': True,
            'work_priority': 'CRM_FIRST', 'live_authorization': 'HOLD_UNVERIFIED',
            'scope': 'static policy declaration, not observed service configuration'}


def evaluate_claimed_signals(signals: dict) -> dict:
    """Theoretical decision model. PASS inputs are untrusted claims, not evidence.

    This function intentionally NEVER returns a live-authorization verdict.
    """
    _exact_keys(signals, SIGNALS, 'signals')
    if any(type(value) is not str or value not in LEVELS for value in signals.values()):
        raise ValueError('invalid_signal_type_or_state')
    crm = signals['crm_independent_acceptance'] == 'PASS'
    site = signals['website_independent_acceptance'] == 'PASS'
    start = signals['owner_integration_start'] == 'PASS'
    if not crm:
        priority = 'CRM_FIRST'
    elif not site:
        priority = 'SITE_SECOND'
    elif not start:
        priority = 'WAIT_OWNER_START'
    else:
        priority = 'INTEGRATION_DESIGN_CANDIDATE'
    all_claimed = all(s == 'PASS' for s in signals.values())
    return {'priority_on_claims': priority, 'start_prerequisites_claimed': crm and site and start,
            'live_prerequisites_claimed': all_claimed,
            'live_authorization': 'HOLD_EXTERNAL_ATTESTATION',
            'proof': 'none; untrusted model inputs'}


def check_source_defaults(root: Path = ROOT) -> None:
    """Sanity check only: production env and network state remain unobserved."""
    template = (root / 'config/env.template').read_text(encoding='utf-8')
    settings = {}
    for line in template.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            raise ValueError('malformed_env_template')
        key, value = line.split('=', 1)
        if key in settings:
            raise ValueError('duplicate_env_template_key')
        settings[key] = value
    for key in ('LEAD_WEBHOOK_URL', 'LEAD_WEBHOOK_SECRET'):
        if key not in settings or settings[key]:
            raise ValueError('live_delivery_in_template:' + key)
    agent = (root / 'AGENTS.md').read_text(encoding='utf-8')
    if 'ADR-0001-INTEGRATION-SEQUENCE.md' not in agent:
        raise ValueError('missing_agent_integration_policy')
    roadmap = (root / 'docs/CRM_INTEGRATION_ROADMAP.md').read_text(encoding='utf-8')
    if 'Owner-approved execution order — HARD DEPENDENCY' not in roadmap:
        raise ValueError('missing_roadmap_stage_gate')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--check-live', action='store_true', help='always HOLD without independent provider verification')
    args = parser.parse_args(argv)
    try:
        policy = unique_json((args.root / 'config/integration-lifecycle.json').read_text(encoding='utf-8'))
        verdict = validate_frozen_policy(policy)
        check_source_defaults(args.root)
    except (ValueError, OSError, UnicodeError) as exc:
        print(json.dumps({'status': 'PLAN_INVALID', 'reason': str(exc)[:160]}, sort_keys=True))
        return 1
    verdict['status'] = 'PLAN_VALID_RELEASE_HOLD'
    print(json.dumps(verdict, sort_keys=True))
    return 2 if args.check_live else 0


if __name__ == '__main__':
    raise SystemExit(main())
