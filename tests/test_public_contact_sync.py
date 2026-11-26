"""Public contact and offline-request behavior in the real page."""
from playwright.sync_api import expect


def test_every_telephone_link_follows_the_public_config(browser, server):
    page = browser.new_page(viewport={"width": 390, "height": 844}, reduced_motion="reduce")
    try:
        config_url = server["base"] + "/api/config"
        config = page.request.get(config_url).json()
        original = config["contacts"]["phone"]
        replacement = "+380000000001"
        assert replacement != original
        config["contacts"]["phone"] = replacement
        page.route(config_url, lambda route: route.fulfill(json=config))
        page.goto(server["base"] + "/")

        dock = page.locator(".dock__call")
        expect(dock).to_have_attribute("href", f"tel:{replacement}")
        expect(dock).to_have_text("Подзвонити")
        unavailable_action = page.locator("#formUnavailable a")
        expect(unavailable_action).to_have_attribute("href", f"tel:{replacement}")
        expect(unavailable_action).to_have_text("Зателефонуйте диспетчеру.")
        expect(page.locator(f'a[href="tel:{original}"]')).to_have_count(0)
        assert all(
            link == f"tel:{replacement}"
            for link in page.locator('a[href^="tel:"]').evaluate_all(
                "(anchors) => anchors.map((anchor) => anchor.getAttribute('href'))"
            )
        )
    finally:
        page.close()


def test_bundle_mode_prepares_a_copy_without_attempting_delivery(browser, server):
    page = browser.new_page(reduced_motion="reduce")
    requests = []

    def prevent_delivery(route):
        requests.append(route.request.url)
        route.abort()

    try:
        page.add_init_script("window.PBT_BUNDLE = true")
        page.route("**/api/lead", prevent_delivery)
        page.goto(server["base"] + "/")
        send = page.locator("#send")
        expect(send).to_have_text("Підготувати заявку")
        page.locator("#subject").fill("Тестова оренда")
        page.locator("#contact").fill("067 000 00 00")
        send.click()

        expect(page.locator("#fallback")).to_be_visible()
        expect(page.locator("#fallback")).to_be_focused()
        expect(page.locator("#fallbackStatus")).to_have_text("Заявку не надіслано")
        expect(page.locator("#fbText")).to_contain_text("Тестова оренда")
        assert not requests
        assert page.evaluate("sessionStorage.getItem('pbt.pendingLead')") is None

        page.locator("#fbRetry").click()
        expect(send).to_be_focused()
        expect(page.locator("#subject")).to_have_value("Тестова оренда")
        expect(page.locator("#formMsg")).to_be_hidden()
    finally:
        page.close()
