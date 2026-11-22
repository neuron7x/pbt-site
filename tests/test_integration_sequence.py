"""Independent controls for the CRM-first, standalone-site-second contract."""
import copy
import itertools
import json
from pathlib import Path
import subprocess
import sys
import unittest

from tools.integration_sequence import (
    SIGNALS, CHANNELS, ROOT, evaluate_claimed_signals,
    unique_json, validate_frozen_policy, check_source_defaults,
)


class IntegrationSequenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = unique_json((ROOT / 'config/integration-lifecycle.json').read_text(encoding='utf-8'))

    def test_canonical_plan_is_valid_but_not_release_accepted(self):
        self.assertEqual(validate_frozen_policy(self.policy)['live_authorization'], 'HOLD_UNVERIFIED')
        self.assertEqual(self.policy['work_priority'], 'CRM_FIRST')
        self.assertFalse(any(self.policy['planned_activation'].values()))

    def test_bad_json_is_rejected_including_duplicate_nested_claims(self):
        for value in ['[]', 'null', 'true', 'NaN', 'Infinity', '{} garbage']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                unique_json(value)
        with self.assertRaisesRegex(ValueError, 'duplicate_key'):
            unique_json('{"completion_signals":{"a":"PASS","a":"UNKNOWN"}}')

    def test_unknown_keys_and_boolean_substitution_are_denied(self):
        changes = [
            lambda p: p.update(extra=True),
            lambda p: p.update(schema_version=True),
            lambda p: p.update(work_priority='INTEGRATION_THIRD'),
            lambda p: p['completion_signals'].update(crm_independent_acceptance=True),
            lambda p: p['completion_signals'].update(owner_integration_start='PASS'),
            lambda p: p['planned_activation'].update(site_to_crm=True),
            lambda p: p['planned_activation'].update(crm_to_site='yes'),
            lambda p: p['planned_activation'].pop('customer_status'),
            lambda p: p['references'].update(jira='https://unverified.invalid/claim'),
            lambda p: p.update(evidence_class='ENGINEERING_ACCEPTED'),
        ]
        for change in changes:
            with self.subTest(change=repr(change)):
                modified = copy.deepcopy(self.policy)
                change(modified)
                with self.assertRaises(ValueError):
                    validate_frozen_policy(modified)

    def test_exhaustive_all_nine_three_state_claim_vectors_never_authorize_live(self):
        # 3^9 = 19683 finite claim vectors; pure model, NOT TLA+/real-system proof.
        count = 0
        for values in itertools.product(('UNKNOWN', 'PASS', 'FAIL'), repeat=len(SIGNALS)):
            claims = dict(zip(SIGNALS, values))
            result = evaluate_claimed_signals(claims)
            self.assertEqual(result['live_authorization'], 'HOLD_EXTERNAL_ATTESTATION')
            self.assertEqual(result['start_prerequisites_claimed'], all(
                claims[key] == 'PASS' for key in SIGNALS[:3]))
            self.assertEqual(result['live_prerequisites_claimed'], all(v == 'PASS' for v in values))
            if claims['crm_independent_acceptance'] != 'PASS':
                self.assertEqual(result['priority_on_claims'], 'CRM_FIRST')
            elif claims['website_independent_acceptance'] != 'PASS':
                self.assertEqual(result['priority_on_claims'], 'SITE_SECOND')
            elif claims['owner_integration_start'] != 'PASS':
                self.assertEqual(result['priority_on_claims'], 'WAIT_OWNER_START')
            else:
                self.assertEqual(result['priority_on_claims'], 'INTEGRATION_DESIGN_CANDIDATE')
            count += 1
        self.assertEqual(count, 19683)

    def test_cli_static_lint_and_release_hold_have_separate_exit_codes(self):
        lint = subprocess.run([sys.executable, str(ROOT / 'tools/integration_sequence.py')], cwd=ROOT,
                              capture_output=True, text=True, timeout=8)
        self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)
        self.assertEqual(json.loads(lint.stdout)['status'], 'PLAN_VALID_RELEASE_HOLD')
        live = subprocess.run([sys.executable, str(ROOT / 'tools/integration_sequence.py'), '--check-live'],
                              cwd=ROOT, capture_output=True, text=True, timeout=8)
        self.assertEqual(live.returncode, 2, live.stdout + live.stderr)
        self.assertEqual(json.loads(live.stdout)['live_authorization'], 'HOLD_UNVERIFIED')

    def test_env_template_and_architecture_discoverability(self):
        check_source_defaults(ROOT)
        text = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
        self.assertIn('опційний', text.lower())
        self.assertIn('лише після', text.lower())

    def test_missing_or_nonempty_webhook_defaults_are_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for rel in ('AGENTS.md', 'docs/CRM_INTEGRATION_ROADMAP.md'):
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / rel).read_bytes())
            (root / 'config').mkdir()
            for values in ['LEAD_WEBHOOK_URL=https://example.invalid\nLEAD_WEBHOOK_SECRET=\n',
                           'LEAD_WEBHOOK_URL=\nLEAD_WEBHOOK_SECRET=abc\n',
                           'LEAD_WEBHOOK_URL=\nLEAD_WEBHOOK_URL=\nLEAD_WEBHOOK_SECRET=\n',
                           'LEAD_WEBHOOK_URL=\n']:
                (root / 'config/env.template').write_text(values)
                with self.subTest(values=values), self.assertRaises(ValueError):
                    check_source_defaults(root)


if __name__ == '__main__':
    unittest.main()
