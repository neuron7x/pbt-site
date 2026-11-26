"""The optional spark canvas must not interrupt page initialization.

Actual sizing/wake/frame functions run against controlled canvas and RAF stubs;
this verifies recovery and scheduling, not browser rendering.
"""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("mode", ["unavailable", "hidden", "desktop", "mobile", "offscreen"])
def test_optional_spark_context_failure_is_inert_and_available_animation_is_preserved(mode):
    node = shutil.which("node")
    assert node, "Node.js is required to verify optional canvas recovery"
    script = r"""
const fs = require('node:fs'), vm = require('node:vm');
const source = fs.readFileSync('web/js/site.js', 'utf8'), mode = process.argv[1];
const functions = ['sparkSize', 'sparkLoop'].map(name => {
  const found = source.match(new RegExp('  function ' + name + '\\([^\\n]*\\) \\{[\\s\\S]*?\\n  \\}'));
  if (!found) throw new Error('Missing actual canvas function: ' + name);
  return found[0];
});
const wake = source.split('\n').find(line => line.trimStart().startsWith('const sparkWake = '));
if (!wake) throw new Error('Missing actual canvas wake policy');
let contextCalls = 0, frames = 0, clears = 0, particles = 0;
const transforms = [];
const drawing = {setTransform: (...args) => transforms.push(args), clearRect: () => {clears++;},
  beginPath() {}, arc() {}, fill: () => {particles++;}};
const spark = {clientWidth: 400, clientHeight: 200, width: 0, height: 0,
  getContext: kind => {contextCalls++; if (kind !== '2d') throw new Error(kind); return mode === 'unavailable' ? null : drawing;}};
// A previously queued frame must also stop if a later measurement loses the context.
const context = {spark, ctx: null, dots: [{stale: true}], cW: 0, cH: 0, cLast: 0, sparkOn: mode === 'unavailable',
  getComputedStyle: () => ({display: mode === 'hidden' ? 'none' : 'block'}), devicePixelRatio: 2,
  mobileLayout: () => mode === 'mobile', motion: () => true, quality: () => 'full', heroP: 0,
  heroInView: () => mode !== 'offscreen',
  document: {hidden: false}, requestAnimationFrame: () => {frames++;}};
vm.runInNewContext(functions.join('\n') + '\n' + wake, context);
let error = null;
try {vm.runInNewContext('sparkSize(); sparkWake(); sparkLoop(100);', context);}
catch (caught) {error = caught.name + ': ' + caught.message;}
process.stdout.write(JSON.stringify({error, contextCalls, frames, clears, particles, transforms,
  width: spark.width, height: spark.height, dots: context.dots.length,
  hasContext: !!context.ctx, running: context.sparkOn}));
"""
    run = subprocess.run([node, "-e", script, mode], cwd=ROOT,
                         capture_output=True, text=True, check=True, timeout=10)
    actual = json.loads(run.stdout)
    assert actual["error"] is None
    if mode in ("unavailable", "hidden"):
        assert not actual["hasContext"] and actual["dots"] == 0
        assert actual["frames"] == actual["particles"] == actual["clears"] == 0
        assert actual["transforms"] == [] and not actual["running"]
        assert actual["contextCalls"] == (0 if mode == "hidden" else 1)
    elif mode == "offscreen":
        assert actual["hasContext"] and not actual["running"]
        assert actual["frames"] == actual["particles"] == actual["clears"] == 0
    else:
        count = 28 if mode == "mobile" else 60
        assert actual["hasContext"] and actual["running"]
        assert actual["dots"] == actual["particles"] == count
        assert actual["frames"] == 2 and actual["clears"] == 1
        assert actual["contextCalls"] == 1
        assert actual["transforms"] == [[1.5, 0, 0, 1.5, 0, 0]]
        assert (actual["width"], actual["height"]) == (600, 300)
