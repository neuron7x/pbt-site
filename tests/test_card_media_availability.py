"""Card and hero video eligibility, pause policy and proof poster loading.

The focused browser cases complement the DOM/media stub checks for bundled clips.
"""
import base64
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("mode,poster", [
    ("standalone-present", "data:image/webp;base64,AAAA"),
    ("standalone-omitted", "data:image/webp;base64,AAAA"),
    ("live", "media/video/proof-amph.webp"),
    ("live", "//example.invalid/poster.webp"),
    ("multifile", "media/video/proof-amph.webp"),
])
def test_card_sources_respect_bundle_availability_and_pause(mode, poster):
    node = shutil.which("node")
    assert node, "Node.js is required to verify card-media availability"
    script = r"""
const fs = require('node:fs'), vm = require('node:vm');
const {attrOk} = require('./web/js/dom.js');
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
  dataset: {video: 'proof-amph', poster: process.argv[2]}, poster: '', src: '', preload: 'none',
  sources: [], playCalls: 0, pauseCalls: 0,
  setAttribute() {}, append(...nodes) {this.sources.push(...nodes);},
  play() {this.playCalls++; return Promise.resolve();}, pause() {this.pauseCalls++;}
};
const classes = new Set(), card = {classList: {add: v => classes.add(v), remove: v => classes.delete(v)}};
const playing = new Set(), visibleCards = new Set();
let allowed = true;
const context = {D, V_BASE: 'media/video/', card, playing, visibleCards, attrOk,
  videoAllowed: () => allowed, $: () => media,
  document: {createElement: tag => tag === 'video' ? {canPlayType: () => 'probably'} : {}}
};
vm.runInNewContext(vsrc + '\n' + functions.join('\n'), context);
const sync = () => vm.runInNewContext('syncCardVideo(card);', context);
const state = () => ({src: media.src, sources: media.sources, ready: !!media.dataset.ready,
  preload: media.preload, poster: media.poster, playCalls: media.playCalls, pauseCalls: media.pauseCalls,
  isPlaying: classes.has('is-playing')});
sync(); const beforeView = state();
visibleCards.add(card); sync(); const initial = state();
allowed = false; sync(); const paused = state();
allowed = true; visibleCards.delete(card); sync(); const offscreen = state();
process.stdout.write(JSON.stringify({beforeView, initial, paused, offscreen}));
"""
    run = subprocess.run([node, "-e", script, mode, poster], cwd=ROOT,
                         capture_output=True, text=True, check=True, timeout=10)
    states = json.loads(run.stdout)
    first = states["initial"]
    available = mode != "standalone-omitted"
    assert states["beforeView"]["poster"] == ""
    assert states["beforeView"]["playCalls"] == 0
    assert first["poster"] == (poster if available and not poster.startswith("//") else "")
    assert first["playCalls"] == int(available)
    assert first["ready"] is available
    assert not first["isPlaying"], "a requested clip has not painted a frame yet"
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
        assert not stopped["isPlaying"], name
        assert stopped["poster"] == first["poster"], name


@pytest.mark.parametrize("mode", ["full", "reduced", "no-observer"])
def test_proof_poster_loads_at_viewport_and_keeps_image_fallback(browser, server, mode):
    context = browser.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=2, is_mobile=True, has_touch=True,
                                  reduced_motion="reduce" if mode == "reduced" else "no-preference")
    try:
        context.add_init_script("""
          Object.defineProperty(navigator, 'hardwareConcurrency', {value: 8});
        """ + ("delete window.IntersectionObserver;" if mode == "no-observer" else ""))
        page = context.new_page()
        page.goto(server["base"], wait_until="load")
        assert page.locator("#reel video[data-poster]").count() == 6
        assert page.locator("#reel video[poster]").count() == 0
        assert page.evaluate(r"""() => !performance.getEntriesByType('resource')
            .some(e => /\/media\/video\/proof-[^/]+\.webp$/.test(e.name))""")
        card = page.locator("#reel .proof-card").first
        card.evaluate("""e => e.scrollIntoView({behavior: 'instant', block: 'center'})""")
        image = card.locator("img")
        page.wait_for_function("""() => document.querySelector("#reel .proof-card img").naturalWidth > 0""")
        video = card.locator("video")
        if mode == "full":
            page.wait_for_function("""() => {
              const video = document.querySelector("#reel .proof-card video");
              return video.currentTime > 0 && !video.paused;
            }""")
            assert video.get_attribute("poster") == image.get_attribute("src")
        else:
            assert video.get_attribute("poster") is None
            assert video.evaluate("video => video.paused && !video.currentSrc")
            assert image.is_visible()
            assert video.evaluate("video => getComputedStyle(video).opacity") == "0"
    finally:
        context.close()


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
let allowed = true, inView = true;
const context = {D, V_BASE: 'media/video/', hVideo: media, innerWidth: width, innerHeight: 844,
  devicePixelRatio: dpr, scrollY: 0, navigator: {connection: {}}, videoAllowed: () => allowed,
  heroInView: () => inView, clearTimeout: () => {},
  document: {createElement: tag => tag === 'video' ? {canPlayType: () => 'probably'} : {}},
  setTimeout: () => {throw new Error('Unexpected retry for the resolved media stub');}
};
vm.runInNewContext(helpers.join('\n') + '\n' + functions.join('\n') + '\nlet tries = 0, retry = 0, pending = false;\n' + go[0], context);
const sync = () => vm.runInNewContext('go();', context);
const state = () => ({src: media.src, sources: media.sources.map(node => ({...node})), ready: !!media.dataset.ready,
  preload: media.preload, poster: media.poster, playCalls: media.playCalls, pauseCalls: media.pauseCalls});
(async () => {
  sync(); await new Promise(setImmediate); const initial = state();
  const attached = vm.runInNewContext("attachVideo(hVideo, 'hero-wide', {tall: true});", context);
  context.scrollY = context.innerHeight + 10; sync(); const sticky = state();
  allowed = false; sync(); const paused = state();
  allowed = true; inView = false; sync(); const offscreen = state();
  inView = true; context.scrollY = 0; sync(); const resumed = state();
  process.stdout.write(JSON.stringify({initial, attached, sticky, paused, offscreen, resumed}));
})().catch(error => { console.error(error); process.exitCode = 1; });
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
    assert states["sticky"]["pauseCalls"] == first["pauseCalls"]
    for name in ("paused", "offscreen"):
        assert states[name]["playCalls"] == first["playCalls"], name
        assert states[name]["pauseCalls"] == int(available), name
    assert states["resumed"]["playCalls"] == int(available) * 2
    for name in ("paused", "offscreen", "resumed"):
        assert states[name]["src"] == first["src"], name
        assert states[name]["sources"] == first["sources"], name
        assert states[name]["ready"] is available, name
        assert states[name]["poster"] == first["poster"], name
