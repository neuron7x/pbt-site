"""Budget-omitted clips stay poster-only in a self-contained export.

These exercise the real card/hero functions with DOM/media stubs, not browser
playback. Live and multi-file paths and the existing pause policy stay intact.
"""
import base64
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("mode", ["standalone-present", "standalone-omitted", "live", "multifile"])
def test_card_sources_respect_bundle_availability_and_pause(mode):
    node = shutil.which("node")
    assert node, "Node.js is required to verify card-media availability"
    script = r"""
const fs = require('node:fs'), vm = require('node:vm');
const source = fs.readFileSync('web/js/site.js', 'utf8');
const functions = ['attachVideo', 'syncCardVideo'].map(name => {
  const found = source.match(new RegExp('  function ' + name + '\\([^\\n]*\\) \\{[\\s\\S]*?\\n  \\}'));
  if (!found) throw new Error('Missing media function: ' + name);
  return found[0];
});
const vsrc = source.split('\n').find(line => line.trimStart().startsWith('const vsrc = '));
if (!vsrc) throw new Error('Missing shared video-source resolver');
const mode = process.argv[1], embedded = 'data:video/mp4;base64,AAAA';
const D = mode.startsWith('standalone') ? {videoData: {}} : {};
if (mode === 'standalone-present') D.videoData['proof-amph.mp4'] = embedded;
if (mode === 'multifile') D.mp4Only = true;
const media = {
  dataset: {video: 'proof-amph'}, poster: 'poster.webp', src: '', preload: 'none',
  sources: [], playCalls: 0, pauseCalls: 0,
  setAttribute() {}, append(...nodes) {this.sources.push(...nodes);},
  play() {this.playCalls++; return Promise.resolve();}, pause() {this.pauseCalls++;}
};
const classes = new Set(), card = {classList: {add: v => classes.add(v), remove: v => classes.delete(v)}};
const playing = new Set(), visibleCards = new Set([card]);
let allowed = true;
const context = {D, V_BASE: 'media/video/', card, playing, visibleCards,
  videoAllowed: () => allowed, $: () => media,
  document: {createElement: tag => tag === 'video' ? {canPlayType: () => 'probably'} : {}}
};
vm.runInNewContext(vsrc + '\n' + functions.join('\n'), context);
const sync = () => vm.runInNewContext('syncCardVideo(card);', context);
const state = () => ({src: media.src, sources: media.sources, ready: !!media.dataset.ready,
  preload: media.preload, poster: media.poster, playCalls: media.playCalls, pauseCalls: media.pauseCalls,
  isPlaying: classes.has('is-playing'), tracked: playing.has(media)});
sync(); const initial = state();
allowed = false; sync(); const paused = state();
allowed = true; visibleCards.delete(card); sync(); const offscreen = state();
process.stdout.write(JSON.stringify({initial, paused, offscreen}));
"""
    run = subprocess.run([node, "-e", script, mode], cwd=ROOT,
                         capture_output=True, text=True, check=True, timeout=10)
    states = json.loads(run.stdout)
    first = states["initial"]
    available = mode != "standalone-omitted"
    assert first["poster"] == "poster.webp"
    assert first["playCalls"] == int(available)
    assert first["ready"] is available
    assert first["isPlaying"] is available and first["tracked"] is available
    if mode == "standalone-omitted":
        assert first["src"] == "" and first["sources"] == []
        assert first["preload"] == "none"
    elif mode == "standalone-present":
        assert first["src"] == "data:video/mp4;base64,AAAA" and first["sources"] == []
    elif mode == "multifile":
        assert first["src"] == "media/video/proof-amph.mp4" and first["sources"] == []
    else:
        assert [s["src"] for s in first["sources"]] == [
            "media/video/proof-amph.webm", "media/video/proof-amph.mp4"]
    for offset, name in enumerate(("paused", "offscreen"), 1):
        stopped = states[name]
        assert stopped["playCalls"] == first["playCalls"], name
        assert stopped["pauseCalls"] == first["pauseCalls"] + offset, name
        assert not stopped["isPlaying"] and not stopped["tracked"], name
        assert stopped["poster"] == first["poster"], name


@pytest.mark.parametrize("mode,width,dpr,rendition", [
    ("standalone-present", 1440, 2, "hero-wide-720"),
    ("standalone-present", 390, 2, "hero-tall"),
    ("standalone-omitted", 1440, 2, "hero-wide-720"),
    ("standalone-omitted", 390, 2, "hero-tall"),
    ("live", 1920, 1, "hero-wide"),
    ("live", 1440, 1, "hero-wide-720"),
    ("live", 390, 2, "hero-tall"),
    ("multifile", 1920, 1, "hero-wide"),
    ("multifile", 390, 2, "hero-tall"),
])
def test_hero_playback_resolves_available_rendition_and_resumes_without_duplicate_sources(mode, width, dpr, rendition):
    node = shutil.which("node")
    assert node, "Node.js is required to verify hero-media availability"
    script = r"""
const fs = require('node:fs'), vm = require('node:vm');
const source = fs.readFileSync('web/js/site.js', 'utf8');
const functions = ['heroHD', 'attachVideo'].map(name => {
  const found = source.match(new RegExp('  function ' + name + '\\([^\\n]*\\) \\{[\\s\\S]*?\\n  \\}'));
  if (!found) throw new Error('Missing hero function: ' + name);
  return found[0];
});
const helpers = ['vsrc', 'mobileLayout'].map(name => {
  const found = source.split('\n').find(line => line.trimStart().startsWith('const ' + name + ' ='));
  if (!found) throw new Error('Missing hero helper: ' + name);
  return found;
});
const go = source.match(/      const go = \(\) => \{[\s\S]*?\n      \};/);
if (!go) throw new Error('Missing actual hero playback closure');
const mode = process.argv[1], width = Number(process.argv[2]), dpr = Number(process.argv[3]);
const D = mode.startsWith('standalone') ? {videoData: {}} : {};
if (mode === 'standalone-present') {
  for (const name of ['hero-wide-720', 'hero-tall'])
    D.videoData[name + '.mp4'] = 'data:video/mp4;base64,' + Buffer.from(name).toString('base64');
}
if (mode === 'multifile') D.mp4Only = true;
const media = {
  dataset: {}, poster: 'hero-poster.webp', src: '', preload: 'none', paused: true,
  sources: [], playCalls: 0, pauseCalls: 0,
  setAttribute() {}, append(...nodes) {this.sources.push(...nodes);},
  play() {this.playCalls++; this.paused = false; return Promise.resolve();},
  pause() {this.pauseCalls++; this.paused = true;}
};
let allowed = true;
const context = {D, V_BASE: 'media/video/', hVideo: media, innerWidth: width, innerHeight: 844,
  devicePixelRatio: dpr, scrollY: 0, navigator: {connection: {}}, videoAllowed: () => allowed,
  document: {createElement: tag => tag === 'video' ? {canPlayType: () => 'probably'} : {}},
  setTimeout: () => {throw new Error('Unexpected retry for the resolved media stub');}
};
vm.runInNewContext(helpers.join('\n') + '\n' + functions.join('\n') + '\nlet tries = 0;\n' + go[0], context);
const sync = () => vm.runInNewContext('go();', context);
const state = () => ({src: media.src, sources: media.sources.map(node => ({...node})), ready: !!media.dataset.ready,
  preload: media.preload, poster: media.poster, playCalls: media.playCalls, pauseCalls: media.pauseCalls});
sync(); const initial = state();
const attached = vm.runInNewContext("attachVideo(hVideo, 'hero-wide', {tall: true});", context);
allowed = false; sync(); const paused = state();
allowed = true; context.scrollY = context.innerHeight; sync(); const offscreen = state();
context.scrollY = 0; sync(); const resumed = state();
process.stdout.write(JSON.stringify({initial, attached, paused, offscreen, resumed}));
"""
    run = subprocess.run([node, "-e", script, mode, str(width), str(dpr)], cwd=ROOT,
                         capture_output=True, text=True, check=True, timeout=10)
    states = json.loads(run.stdout)
    first = states["initial"]
    available = mode != "standalone-omitted"
    assert first["playCalls"] == int(available)
    assert first["ready"] is available
    assert states["attached"] is available
    assert first["poster"] == "hero-poster.webp"
    if mode == "standalone-omitted":
        assert first["src"] == "" and first["sources"] == []
        assert first["preload"] == "none"
    elif mode == "standalone-present":
        encoded = base64.b64encode(rendition.encode()).decode()
        assert first["src"] == "data:video/mp4;base64," + encoded
        assert first["sources"] == []
    elif mode == "multifile":
        assert first["src"] == f"media/video/{rendition}.mp4" and first["sources"] == []
    else:
        assert [s["src"] for s in first["sources"]] == [
            f"media/video/{rendition}.webm", f"media/video/{rendition}.mp4"]
    for offset, name in enumerate(("paused", "offscreen"), 1):
        assert states[name]["playCalls"] == first["playCalls"], name
        assert states[name]["pauseCalls"] == first["pauseCalls"] + offset, name
    assert states["resumed"]["playCalls"] == int(available) * 2
    for name in ("paused", "offscreen", "resumed"):
        assert states[name]["src"] == first["src"], name
        assert states[name]["sources"] == first["sources"], name
        assert states[name]["ready"] is available, name
        assert states[name]["poster"] == first["poster"], name
