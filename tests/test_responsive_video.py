"""Формат кадру підлаштовується без перезавантаження сторінки."""

from playwright.sync_api import expect


def test_hero_reselects_format_on_rotation_and_keeps_playing(page_factory):
    page = page_factory(390, 844, mobile=True, dpr=1)
    video = page.locator("#heroVideo")
    expect(video).to_have_js_property("videoHeight", 1280, timeout=10000)
    page.wait_for_function("() => document.querySelector('#heroVideo').currentTime > 1")
    position = video.evaluate("node => node.currentTime")

    page.set_viewport_size({"width": 844, "height": 390})
    expect(video).to_have_js_property("videoHeight", 720, timeout=10000)
    assert video.evaluate("node => /hero-wide-720\\.(mp4|webm)$/.test(node.currentSrc)")
    page.wait_for_function("() => { const v = document.querySelector('#heroVideo'); return !v.paused && !v.seeking && v.readyState >= 2; }")
    assert video.evaluate("node => node.currentTime") >= position - 0.15
    assert video.locator("source").count() <= 2

    page.set_viewport_size({"width": 390, "height": 844})
    expect(video).to_have_js_property("videoHeight", 1280, timeout=10000)
    page.wait_for_function("() => !document.querySelector('#heroVideo').paused")
    assert video.locator("source").count() <= 2


def test_cold_landscape_uses_wide_rendition(page_factory):
    page = page_factory(844, 390, mobile=True, dpr=1)
    video = page.locator("#heroVideo")
    expect(video).to_have_js_property("videoHeight", 720, timeout=10000)
    assert video.evaluate("node => /hero-wide-720\\.(mp4|webm)$/.test(node.currentSrc)")


def test_cine_reselects_format_for_the_active_chapter(page_factory):
    page = page_factory(390, 844, mobile=True)
    chapter = page.locator("#cine-karier")
    active = page.locator("#masshtab .cine__v.is-on")
    chapter.evaluate("node => node.scrollIntoView({behavior: 'instant', block: 'center'})")
    expect(active).to_have_js_property("videoHeight", 1280, timeout=10000)
    page.wait_for_function("() => document.querySelector('#masshtab .cine__v.is-on').currentTime > 1")
    position = active.evaluate("node => node.currentTime")

    page.set_viewport_size({"width": 844, "height": 390})
    chapter.evaluate("node => node.scrollIntoView({behavior: 'instant', block: 'center'})")
    expect(page.locator("#masshtab")).to_have_attribute("data-cur", "karier")
    expect(active).to_have_js_property("videoHeight", 1080, timeout=10000)
    assert active.evaluate("node => node.currentSrc.includes('/karier-w.')")
    page.wait_for_function("() => { const v = document.querySelector('#masshtab .cine__v.is-on'); return !v.paused && !v.seeking && v.readyState >= 2; }")
    assert active.evaluate("node => node.currentTime") >= position - 0.15


def test_cine_keeps_position_if_an_intermediate_rendition_is_still_loading(page_factory):
    page = page_factory(390, 844, mobile=True)
    chapter = page.locator("#cine-karier")
    active = page.locator("#masshtab .cine__v.is-on")
    chapter.evaluate("node => node.scrollIntoView({behavior: 'instant', block: 'center'})")
    expect(active).to_have_js_property("videoHeight", 1280, timeout=10000)
    page.wait_for_function("() => document.querySelector('#masshtab .cine__v.is-on').currentTime > 1.5")
    position = active.evaluate("node => node.currentTime")

    def hold_wide_video(route):
        if route.request.url.endswith(("karier-w.mp4", "karier-w.webm")):
            return
        route.continue_()

    page.route("**/karier-w.*", hold_wide_video)
    with page.expect_request(lambda request: request.url.endswith(("karier-w.mp4", "karier-w.webm"))):
        page.set_viewport_size({"width": 844, "height": 390})
        chapter.evaluate("node => node.scrollIntoView({behavior: 'instant', block: 'center'})")
        expect(active).to_have_attribute("data-clip", "karier-w")
    assert active.evaluate("node => node.readyState") == 0

    page.set_viewport_size({"width": 390, "height": 844})
    chapter.evaluate("node => node.scrollIntoView({behavior: 'instant', block: 'center'})")
    expect(active).to_have_attribute("data-clip", "karier-m")
    expect(active).to_have_js_property("videoHeight", 1280, timeout=10000)
    page.wait_for_function("() => { const v = document.querySelector('#masshtab .cine__v.is-on'); return !v.paused && !v.seeking && v.readyState >= 2; }")
    assert active.evaluate("node => node.currentTime") >= position - 0.15
