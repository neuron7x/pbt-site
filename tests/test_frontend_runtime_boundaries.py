"""Execute real frontend functions with controlled DOM/network/locale adapters.

These are recovery and contract probes, not browser playback, visual or WCAG
evidence. The API payload and receipt prefix remain the existing PBT contract.
"""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def node_probe(script, *args):
    node = shutil.which('node')
    assert node, 'Node.js is required to verify frontend runtime contracts'
    run = subprocess.run([node, '-e', script, *args], cwd=ROOT, capture_output=True,
                         text=True, check=True, timeout=10)
    return json.loads(run.stdout)


def submission_probe(receipt, status=201):
    return node_probe(r"""
const fs = require('node:fs'), vm = require('node:vm');
const source = fs.readFileSync('web/js/site.js', 'utf8');
const submit = source.match(/  form\.addEventListener\('submit', async e => \{[\s\S]*?\n  \}\);/);
const human = source.match(/  function humanText\([^\n]*\) \{[\s\S]*?\n  \}/);
const labels = source.split('\n').find(line => line.trimStart().startsWith('const typeLabel ='));
if (!submit || !human || !labels) throw new Error('Actual form recovery source missing');
const classList = () => ({values: new Set(), add(v) {this.values.add(v);}, remove(v) {this.values.delete(v);}});
const button = {disabled: false, textContent: ''};
const done = {classList: classList(), focus() {this.focused = true;}};
const fallback = {classList: classList(), focus() {this.focused = true;}};
const msg = {classList: classList(), textContent: ''};
const reference = {textContent: ''}, copied = {textContent: ''};
const elements = {'#send': button, '#ref': reference, '#fbText': copied};
let handler, clearCount = 0, fetchCount = 0, timers = 0;
const form = {hidden: false, querySelector() {return null;}, addEventListener(_, f) {handler = f;}};
const payload = {type:'rent', subject:'Synthetic receipt control', contact:'+380670000000', method:'phone'};
const context = {form, done, fallback, msg, $: s => elements[s], payload: () => payload,
  validate: () => ({}), setErr() {}, AbortController, window: {PBT_BUNDLE: false},
  idemKey: 'synthetic-receipt-key-000001', bindIdempotencyKey: async () => {},
  pendingClear() {clearCount++;}, setTimeout() {timers++; return 1;}, clearTimeout() {timers--;},
  fetch: async () => {fetchCount++; return {status:Number(process.argv[2]), json:async () => JSON.parse(process.argv[1])};}};
vm.runInNewContext(labels + '\n' + human[0] + '\n' + submit[0], context);
(async () => {
  await handler({preventDefault() {}});
  process.stdout.write(JSON.stringify({clearCount, fetchCount, disabled:button.disabled,
    success:done.classList.values.has('is-on'), doneFocused:!!done.focused,
    fallback:fallback.classList.values.has('is-on'), fallbackFocused:!!fallback.focused,
    copied:copied.textContent, reference:reference.textContent, timers,
    error:msg.classList.values.has('is-on'), message:msg.textContent}));
})();
""", json.dumps(receipt), str(status))


@pytest.mark.parametrize('receipt,accepted', [
    ({'ok': True, 'ref': 'PBT-000001'}, True),
    ({'ok': True, 'ref': 'PBT-123456'}, True),
    ({'ok': True, 'ref': 'PBT-1000001', 'replayed': True}, True),
    ({'ok': True, 'ref': 'PBT-1'}, False),
    ({'ok': True, 'ref': 'PBT-000000'}, False),
    ({'ok': True, 'ref': 'PBT-0000000'}, False),
    ({'ok': 'false', 'ref': 'PBT-123456'}, False),
    ({'ok': 1, 'ref': 'PBT-123456'}, False),
    ({'ok': {}, 'ref': 'PBT-123456'}, False),
    ({'ok': False, 'ref': 'PBT-123456'}, False),
    ({'ok': True}, False),
    ({'ok': True, 'ref': None}, False),
    ({'ok': True, 'ref': 123456}, False),
    ({'ok': True, 'ref': 'other-123456'}, False),
    ({'ok': True, 'ref': 'PBT-123456 extra'}, False),
    (None, False),
    ([], False),
])
def test_unverified_201_receipt_never_confirms_or_clears_safe_retry(receipt, accepted):
    actual = submission_probe(receipt)
    assert actual['fetchCount'] == 1
    assert not actual['disabled'] and actual['timers'] == 0
    assert actual['success'] is accepted and actual['doneFocused'] is accepted
    assert actual['clearCount'] == int(accepted)
    assert actual['fallback'] is (not accepted)
    if accepted:
        assert actual['reference'] == '№ ' + receipt['ref'][4:]
    else:
        assert actual['fallbackFocused']
        assert 'Synthetic receipt control' in actual['copied']
        assert actual['reference'] == ''


def test_reserved_200_honeypot_receipt_preserves_existing_rejection_behavior():
    actual = submission_probe({'ok': True, 'ref': 'PBT-000000'}, status=200)
    assert actual['fetchCount'] == 1
    assert not actual['disabled'] and actual['timers'] == 0
    assert not actual['success'] and not actual['doneFocused']
    assert actual['clearCount'] == 0 and actual['reference'] == ''
    assert actual['error'] and actual['message']
    assert not actual['fallback'] and not actual['fallbackFocused']


@pytest.mark.parametrize('locale', ['en-CA', 'en-US', 'en-GB', 'ar-EG'])
@pytest.mark.parametrize('zone_alias', [False, True], ids=['kyiv', 'kiev-alias'])
@pytest.mark.parametrize('instant,today,yesterday', [
    ('2026-03-28T22:30:00Z', '2026-03-29', '2026-03-28'),
    ('2026-10-24T21:30:00Z', '2026-10-25', '2026-10-24'),
    ('2026-12-31T22:30:00Z', '2027-01-01', '2026-12-31'),
])
def test_kyiv_date_contract_survives_locale_fallback(locale, zone_alias, instant, today, yesterday):
    actual = node_probe(r"""
const fs = require('node:fs'), vm = require('node:vm');
const source = fs.readFileSync('web/js/site.js', 'utf8');
const start = source.indexOf('  const kyivToday = () => {');
const end = source.indexOf('  /* ───── ЗАЯВКА', start);
if (start < 0 || end < 0) throw new Error('Actual civil-date validator missing');
const [locale, alias, instant, today, yesterday] = process.argv.slice(1);
const NativeDate = Date, NativeFormat = Intl.DateTimeFormat;
class Clock extends NativeDate {constructor(...args) {super(...(args.length ? args : [instant]));}}
const intl = {DateTimeFormat: function (_, options) {
  if (alias === 'true' && options.timeZone === 'Europe/Kyiv') throw new RangeError('Older zone names');
  return new NativeFormat(locale, options);
}};
const context = {Date:Clock, Intl:intl, window:{}};
vm.runInNewContext(source.slice(start, end), context);
const date = value => context.window.PBTv('date', value);
process.stdout.write(JSON.stringify({today:date(today), yesterday:date(yesterday),
  future:date('2999-01-01'), malformed:date('2026-02-30')}));
""", locale, str(zone_alias).lower(), instant, today, yesterday)
    assert actual == {'today': True, 'yesterday': False, 'future': True, 'malformed': False}
