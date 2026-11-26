"""Відтворення кліпів і стабільний кадр у браузері."""

import pytest
from playwright.sync_api import expect


def test_short_mobile_hero_keeps_playing_while_visible(page_factory):
    page = page_factory(375, 667, mobile=True)
    video = page.locator("#heroVideo")
    page.wait_for_function("() => document.querySelector('#heroVideo').currentTime > 0")
    assert page.locator("#hero").evaluate("node => getComputedStyle(node).position") == "relative"

    page.evaluate("scrollTo({top: 64, behavior: 'instant'})")
    page.wait_for_function("() => scrollY >= 60")
    page.wait_for_timeout(250)
    assert page.locator("#hero").evaluate("node => node.getBoundingClientRect().bottom > 300")
    assert not video.evaluate("node => node.paused")

    page.evaluate("scrollTo({top: document.querySelector('#roboty').offsetTop + 160, behavior: 'instant'})")
    page.wait_for_function("() => document.querySelector('#hero').getBoundingClientRect().bottom <= 0")
    page.wait_for_function("() => document.querySelector('#heroVideo').paused")
    page.evaluate("scrollTo({top: 0, behavior: 'instant'})")
    page.wait_for_function("() => !document.querySelector('#heroVideo').paused")


def test_hero_initially_offscreen_attaches_on_return(page_factory):
    page = page_factory(init_script="""
        addEventListener('load', () => {
          scrollTo({top: document.querySelector('#roboty').offsetTop + 160, behavior: 'instant'});
        }, {once: true});
    """)
    page.wait_for_function("() => document.querySelector('#top').getBoundingClientRect().bottom <= 0")
    page.wait_for_timeout(1100)
    video = page.locator("#heroVideo")
    assert not video.evaluate("node => node.currentSrc")
    logo = page.locator("#logoAnim")
    assert logo.get_attribute("src") is None

    page.evaluate("scrollTo({top: 0, behavior: 'instant'})")
    expect(video).to_have_attribute("data-ready", "1")
    expect(logo).to_have_attribute("src", "media/logo/plainbud-logo.webm")
    page.wait_for_function("() => document.querySelector('#heroVideo').currentTime > 0")
    page.wait_for_function("() => document.querySelector('#logoAnim').ended")
    expect(page.locator(".logo-hero")).not_to_have_class("logo-hero is-anim")


def test_card_keeps_photo_until_clip_can_play(page_factory):
    page = page_factory(init_script="""
        const play = HTMLMediaElement.prototype.play;
        HTMLMediaElement.prototype.play = function () {
          if (this.dataset.video === 'proof-amph') {
            this.dataset.blocked = '1';
            return Promise.reject(new DOMException('Test blocks the clip', 'NotAllowedError'));
          }
          return play.call(this);
        };
    """)
    card = page.locator("#reel .proof-card").first
    card.evaluate("node => node.scrollIntoView({behavior: 'instant', block: 'center'})")
    video = card.locator("video")
    expect(video).to_have_attribute("data-blocked", "1")
    assert not card.evaluate("node => node.classList.contains('is-playing')")
    expect(card.locator("img")).to_be_visible()


def test_cine_cancels_next_clip_when_leaving_scene(page_factory):
    page = page_factory()
    first = page.locator("#cine-karier")
    first.evaluate("node => node.scrollIntoView({behavior: 'instant', block: 'center'})")
    expect(page.locator("#masshtab")).to_have_attribute("data-cur", "karier")
    expect(page.locator("#masshtab video.is-on")).to_have_attribute("data-clip", "karier-w")

    page.evaluate("scrollTo({top: 0, behavior: 'instant'})")
    page.wait_for_function("() => document.querySelector('#masshtab').getBoundingClientRect().top > innerHeight")
    page.wait_for_timeout(1650)
    assert page.locator('#masshtab video[data-clip="zemlia-w"]').count() == 0
    assert page.locator("#masshtab video").evaluate_all("nodes => nodes.every(node => node.paused)")

    first.evaluate("node => node.scrollIntoView({behavior: 'instant', block: 'center'})")
    page.wait_for_function("() => !document.querySelector('#masshtab video.is-on').paused")


@pytest.mark.parametrize("reduced", [False, True])
def test_paused_track_keeps_texture_still_but_reports_progress(page_factory, reduced):
    page = page_factory(1440, 900, reduced=reduced)
    if not reduced:
        page.locator("#motionToggle").click()
    track = page.locator("#track")
    state = "() => ['--tx', '--rot', '--tp'].map(name => document.querySelector('#track').style.getPropertyValue(name))"
    first = page.evaluate(state)
    page.evaluate("scrollTo({top: 517, behavior: 'instant'})")
    page.wait_for_function("(previous) => document.querySelector('#track').style.getPropertyValue('--tp') !== previous", arg=first[2])
    page.wait_for_timeout(130)
    still = page.evaluate(state)
    assert still[:2] == first[:2]
    assert float(still[2]) > float(first[2])

    if not reduced:
        page.locator("#motionToggle").click()
        page.wait_for_timeout(100)
        assert page.evaluate(state)[:2] == still[:2]
        page.evaluate("scrollTo({top: 867, behavior: 'instant'})")
        page.wait_for_function("(previous) => document.querySelector('#track').style.getPropertyValue('--rot') !== previous", arg=still[1])
    assert track.get_attribute("aria-hidden") == "true"
