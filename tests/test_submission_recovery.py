"""Actual submit-handler recovery when preparing a safe request key fails.

DOM and network dependencies are controlled stubs; these do not claim browser
interaction or delivery. No request may be sent before key preparation succeeds.
"""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("outcome", ["prepare-failure", "network-failure", "success", "invalid"])
def test_submit_preparation_and_delivery_failures_recover_without_false_success(outcome):
    node = shutil.which("node")
    assert node, "Node.js is required to verify submit-handler recovery"
    script = r"""
const fs = require('node:fs'), vm = require('node:vm');
const source = fs.readFileSync('web/js/site.js', 'utf8'), outcome = process.argv[1];
const submit = source.match(/  form\.addEventListener\('submit', async e => \{[\s\S]*?\n  \}\);/);
const humanText = source.match(/  function humanText\([^\n]*\) \{[\s\S]*?\n  \}/);
const labels = source.split('\n').find(line => line.trimStart().startsWith('const typeLabel = '));
const showFallback = source.match(/  function showLeadFallback\([^\n]*\) \{[\s\S]*?\n  \}/);
if (!submit || !humanText || !labels || !showFallback) throw new Error('Missing actual submit handler or fallback text');
const classList = () => ({values: new Set(), add(x) {this.values.add(x);}, remove(x) {this.values.delete(x);}});
const button = {disabled: false, textContent: 'Надіслати заявку'};
const fallback = {classList: classList(), focus() {this.focused = true;}};
const done = {classList: classList(), focus() {this.focused = true;}};
const message = {textContent: '', classList: classList()};
const copied = {textContent: ''}, reference = {textContent: ''};
let handler, focusedInvalid = false, prepared = false, keyCalls = 0, fetchCalls = 0, cleared = 0, prevented = 0;
const form = {hidden: false, querySelector() {return {focus() {focusedInvalid = true;}};},
  addEventListener(event, callback) {if (event !== 'submit') throw new Error(event); handler = callback;}};
const payload = {type: 'rent', subject: 'Synthetic recovery request', hours: '8', km: '', place: '', date: '',
  name: '', method: 'phone', contact: '+380670000000', comment: '', website: ''};
const timers = new Set(), sentKeys = [];
let timerId = 0;
const elements = {'#send': button, '#fbText': copied, '#ref': reference};
const context = {
  form, done, fallback, msg: message, $: selector => elements[selector], payload: () => payload,
  validate: () => outcome === 'invalid' ? {contact: 'Invalid test contact'} : {}, setErr() {},
  idemKey: null, AbortController, offlineLead: false,
  bindIdempotencyKey: async () => {
    keyCalls++;
    if (outcome === 'prepare-failure') throw new Error('Key preparation failed');
    prepared = true; context.idemKey = 'synthetic-opaque-key-000001';
  },
  pendingClear: () => {cleared++;},
  setTimeout: () => {timers.add(++timerId); return timerId;}, clearTimeout: id => timers.delete(id),
  fetch: async (url, options) => {
    fetchCalls++; sentKeys.push(options.headers['Idempotency-Key']);
    if (!prepared || options.headers['Idempotency-Key'] !== context.idemKey || !context.idemKey)
      throw new Error('Attempted delivery before safe key preparation');
    if (url !== '/api/lead' || options.method !== 'POST') throw new Error('Changed delivery contract');
    if (outcome === 'network-failure') throw new Error('Synthetic lost connection');
    return {status: 201, json: async () => ({ok: true, ref: 'PBT-123456'})};
  }
};
vm.runInNewContext(labels + '\n' + humanText[0] + '\n' + showFallback[0] + '\n' + submit[0], context);
(async () => {
  let rejection = null;
  try {await handler({preventDefault() {prevented++;}});} catch (error) {rejection = error.message;}
  process.stdout.write(JSON.stringify({rejection, prevented, keyCalls, fetchCalls, sentKeys, cleared,
    disabled: button.disabled, button: button.textContent, formHidden: form.hidden,
    fallback: fallback.classList.values.has('is-on'), fallbackFocused: !!fallback.focused,
    done: done.classList.values.has('is-on'), reference: reference.textContent,
    copied: copied.textContent, focusedInvalid, activeTimers: timers.size}));
})();
"""
    run = subprocess.run([node, "-e", script, outcome], cwd=ROOT,
                         capture_output=True, text=True, check=True, timeout=10)
    actual = json.loads(run.stdout)
    assert actual["rejection"] is None
    assert actual["prevented"] == 1
    assert actual["disabled"] is False and actual["button"] == "Надіслати заявку"
    assert actual["activeTimers"] == 0
    if outcome == "invalid":
        assert actual["keyCalls"] == actual["fetchCalls"] == 0
        assert actual["focusedInvalid"] and not actual["formHidden"]
        assert not actual["fallback"] and not actual["done"]
    else:
        assert actual["keyCalls"] == 1
        assert actual["fetchCalls"] == (0 if outcome == "prepare-failure" else 1)
        assert actual["sentKeys"] == ([] if outcome == "prepare-failure" else ["synthetic-opaque-key-000001"])
        assert actual["formHidden"]
        if outcome == "success":
            assert actual["done"] and not actual["fallback"] and actual["cleared"] == 1
            assert actual["reference"] == "№ 123456"
        else:
            assert actual["fallback"] and actual["fallbackFocused"]
            assert not actual["done"] and actual["cleared"] == 0
            assert "Synthetic recovery request" in actual["copied"] and "+380670000000" in actual["copied"]
