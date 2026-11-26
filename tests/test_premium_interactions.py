"""Заявка з картки, відновлювана мережа й керована користувачем пауза."""

import sqlite3

import pytest
from playwright.sync_api import expect


def test_every_material_opens_its_request_without_sending(page_factory):
    page = page_factory(reduced=True)
    requests = []
    page.on("request", lambda request: requests.append(request) if "/api/lead" in request.url else None)
    cards = page.locator("#mats .tile")
    assert cards.count() == 8
    assert cards.get_by_role("button", name="У заявку", exact=True).count() == 8
    for card in cards.all():
        name = card.locator("h3").text_content()
        card.get_by_role("button", name="У заявку", exact=True).click()
        expect(page.locator("#subject")).to_have_value(name)
        expect(page.locator('input[name="type"][value="material"]')).to_be_checked()
    assert requests == []


def test_fleet_without_specs_has_existing_category_purpose(page_factory):
    page = page_factory(reduced=True)
    assert page.locator("#park dl:empty").count() == 0
    missing = page.evaluate("PBT.fleet.filter(unit => !unit.specs.length).map(unit => ({id: unit.id, name: unit.name}))")
    assert len(missing) == 4
    for unit in missing:
        card = page.locator(f'#park [data-id="{unit["id"]}"]')
        if 'мульчер' in unit['name'].lower():
            expect(card.locator(".unit__purpose")).to_have_text('Мульчування порослі.')
            assert 'бетон' not in card.locator('.unit__purpose').inner_text().lower()
        else:
            assert 'дробарк' in unit['name'].lower()
            expect(card.locator(".unit__purpose")).to_have_text('Дроблення бетону й каменю.')
            assert 'мульч' not in card.locator('.unit__purpose').inner_text().lower()
        expect(card.get_by_role("button", name="У заявку", exact=True)).to_be_visible()


def test_retry_preserves_payload_and_idempotency_key(page_factory):
    page = page_factory(reduced=True)
    sent = []

    def reject(route):
        sent.append((route.request.headers["idempotency-key"], route.request.post_data))
        route.abort()

    page.route("**/api/lead", reject)
    page.fill("#subject", "Пісок кар’єрний жовтий")
    page.fill("#contact", "097 863 77 77")
    page.click("#send")
    expect(page.locator("#fallback")).to_have_class("fallback is-on")
    expect(page.locator("#done")).not_to_have_class("done is-on")
    page.click("#fbRetry")
    expect(page.locator("#subject")).to_have_value("Пісок кар’єрний жовтий")
    expect(page.locator("#contact")).to_have_value("097 863 77 77")
    page.click("#send")
    expect(page.locator("#fallback")).to_have_class("fallback is-on")
    assert len(sent) == 2 and sent[0] == sent[1]


def test_stalled_request_times_out_and_can_be_retried(page_factory):
    page = page_factory(reduced=True)
    pending = []
    page.route("**/api/lead", lambda route: pending.append(route))
    page.clock.install()
    page.fill("#subject", "Екскаватор, зміна")
    page.fill("#contact", "097 863 77 77")
    page.click("#send")
    expect(page.locator("#send")).to_be_disabled()
    page.clock.fast_forward(16000)
    expect(page.locator("#fallback")).to_have_class("fallback is-on")
    expect(page.locator("#done")).not_to_have_class("done is-on")
    page.click("#fbRetry")
    expect(page.locator("#send")).to_be_enabled()
    expect(page.locator("#subject")).to_have_value("Екскаватор, зміна")


def test_motion_pause_survives_scroll_and_reload_then_resumes(page_factory):
    page = page_factory()
    page.wait_for_function("() => document.querySelector('#heroVideo').currentTime > 0")
    page.locator("#motionToggle").click()
    expect(page.locator("html")).to_have_attribute("data-motion", "paused")
    expect(page.locator("#motionToggle")).to_have_attribute("aria-pressed", "true")
    page.evaluate("document.querySelector('#cine-voda').scrollIntoView({behavior:'instant'})")
    page.wait_for_timeout(500)
    assert page.evaluate("[...document.querySelectorAll('video')].every(video => video.paused)")
    page.reload(wait_until="networkidle")
    expect(page.locator("html")).to_have_attribute("data-motion", "paused")
    page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
    page.locator("#motionToggle").click()
    expect(page.locator("html")).not_to_have_attribute("data-motion", "paused")
    page.wait_for_function("() => !document.querySelector('#heroVideo').paused")


def test_reduced_motion_cannot_be_overridden_by_manual_control(page_factory):
    page = page_factory(reduced=True)
    expect(page.locator("#motionToggle")).to_be_disabled()
    page.evaluate("document.querySelector('#motionToggle').click()")
    page.evaluate("document.querySelector('#cine-voda').scrollIntoView({behavior:'instant'})")
    assert page.evaluate("[...document.querySelectorAll('video')].every(video => video.paused && !video.currentSrc)")


def test_pause_below_hero_keeps_returned_heading_visible(page_factory):
    page = page_factory()
    page.evaluate("document.querySelector('#cine-voda').scrollIntoView({behavior:'instant'})")
    page.locator("#motionToggle").click()
    page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
    page.wait_for_function("() => getComputedStyle(document.querySelector('#heroCenter')).opacity === '1'")
    assert page.evaluate("document.getAnimations().every(a => a.effect.getTiming().iterations !== Infinity || a.playState !== 'running')")
    assert page.evaluate("[...document.querySelectorAll('video')].every(video => video.paused)")


def test_new_material_request_after_success_gets_distinct_key_and_row(page_factory, server):
    page = page_factory()
    page.locator("#motionToggle").click()
    sent = []
    page.on("request", lambda request: sent.append(request.headers["idempotency-key"]) if "/api/lead" in request.url else None)
    material = page.locator("#mats .tile").first.get_by_role("button", name="У заявку", exact=True)
    with sqlite3.connect(server["db"]) as db:
        before = db.execute("SELECT count(*) FROM leads").fetchone()[0]
    material.click()
    page.fill("#contact", "097 863 77 77")
    page.click("#send")
    expect(page.locator("#done")).to_have_class("done is-on")
    assert page.locator("#done .check path").evaluate("element => parseFloat(getComputedStyle(element).strokeDashoffset)") == 0
    first_ref = page.locator("#ref").text_content()
    material.click()
    page.click("#send")
    expect(page.locator("#done")).to_have_class("done is-on")
    assert len(sent) == 2 and sent[0] != sent[1]
    assert page.locator("#ref").text_content() != first_ref
    with sqlite3.connect(server["db"]) as db:
        assert db.execute("SELECT count(*) FROM leads").fetchone()[0] == before + 2


def test_same_material_after_uncertain_delivery_preserves_key(page_factory):
    page = page_factory(reduced=True)
    sent = []

    def reject(route):
        sent.append((route.request.headers["idempotency-key"], route.request.post_data))
        route.abort()

    page.route("**/api/lead", reject)
    material = page.locator("#mats .tile").first.get_by_role("button", name="У заявку", exact=True)
    material.click()
    page.fill("#contact", "097 863 77 77")
    page.click("#send")
    expect(page.locator("#fallback")).to_have_class("fallback is-on")
    material.click()
    page.click("#send")
    expect(page.locator("#fallback")).to_have_class("fallback is-on")
    assert len(sent) == 2 and sent[0] == sent[1]


def test_mobile_modal_makes_motion_control_inert_and_restores_it(page_factory):
    page = page_factory(390, 844, mobile=True)
    page.locator(".burger").click()
    expect(page.locator("#menu")).to_be_visible()
    assert page.locator("#motionToggle").evaluate("element => element.inert")
    assert page.locator(".skip").evaluate("element => element.inert")
    page.locator("#motionToggle").evaluate("element => element.focus()")
    assert page.evaluate("document.activeElement.closest('#menu') !== null")
    page.keyboard.press("Escape")
    assert not page.locator("#motionToggle").evaluate("element => element.inert")
    page.locator("#motionToggle").click()
    expect(page.locator("html")).to_have_attribute("data-motion", "paused")


def test_full_profile_tracks_system_motion_preference_without_reloading(page_factory):
    page = page_factory()
    page.wait_for_function("() => !document.querySelector('#heroVideo').paused")
    page.emulate_media(reduced_motion="reduce")
    expect(page.locator("#motionToggle")).to_be_disabled()
    assert page.evaluate("[...document.querySelectorAll('video')].every(video => video.paused)")
    page.emulate_media(reduced_motion="no-preference")
    expect(page.locator("#motionToggle")).to_be_enabled()
    page.wait_for_function("() => !document.querySelector('#heroVideo').paused")


def test_explicit_static_quality_is_not_reenabled_by_system_change(page_factory):
    page = page_factory()
    page.evaluate("document.documentElement.dataset.quality = 'static'")
    page.emulate_media(reduced_motion="reduce")
    expect(page.locator("#motionToggle")).to_be_disabled()
    page.emulate_media(reduced_motion="no-preference")
    expect(page.locator("#motionToggle")).to_be_disabled()
    expect(page.locator("html")).to_have_attribute("data-quality", "static")
    assert page.evaluate("[...document.querySelectorAll('video')].every(video => video.paused)")


@pytest.mark.parametrize("selector,open_menu,anchor", [
    ("#heroCenter a[data-req]", False, True),
    ("#mats .tile:first-child button[data-req]", False, False),
    ('#menu a[href="#zapyt"]', True, True),
])
def test_mobile_request_cta_brings_focused_subject_below_navigation(page_factory, selector, open_menu, anchor):
    page = page_factory(390, 844, mobile=True, reduced=True)
    page.locator("#name").fill("Перевірка інтерфейсу")
    page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
    page.wait_for_function("() => scrollY === 0 && document.querySelector('.burger').getBoundingClientRect().top >= 0")
    if open_menu:
        page.locator(".burger").click()
    page.locator(selector).click()
    page.wait_for_function("""() => {
      const field = document.querySelector('#subject');
      const bounds = field.getBoundingClientRect();
      const clearance = parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop);
      return document.activeElement === field && bounds.top >= clearance && bounds.bottom <= innerHeight;
    }""", timeout=1500)
    expect(page.locator("#name")).to_have_value("Перевірка інтерфейсу")
    if anchor:
        assert page.url.endswith("#zapyt")


@pytest.mark.parametrize('theme', ['sky', 'precision'])
def test_explicit_static_quality_stops_motion_without_system_event(page_factory, theme):
    page = page_factory()
    page.locator(f'[data-theme-choice="{theme}"]').click()
    page.wait_for_function("() => !document.querySelector('#heroVideo').paused")
    page.evaluate("document.documentElement.dataset.quality = 'static'")
    expect(page.locator('html')).to_have_attribute('data-motion', 'paused')
    expect(page.locator('#motionToggle')).to_be_disabled()
    assert page.evaluate("[...document.querySelectorAll('video')].every(video => video.paused)")
    assert page.evaluate("document.getAnimations().every(a => a.playState != 'running')")
    page.evaluate("document.documentElement.dataset.quality = 'full'")
    expect(page.locator('html')).to_have_attribute('data-motion', 'running')
    page.wait_for_function("() => !document.querySelector('#heroVideo').paused")
