"""WCAG 2.2: текст помилок пов'язаний із полями, фокус завжди відомий."""


def test_invalid_contact_has_programmatic_error_description(page_factory):
    pg = page_factory(390, 844, mobile=True, reduced=True)
    pg.fill("#contact", "12345")
    pg.fill("#hours", "0")
    pg.click("#send")
    for ident in ("contact", "hours"):
        field = pg.locator("#" + ident)
        assert field.get_attribute("aria-invalid") == "true"
        error_id = "error-" + ident
        assert error_id in (field.get_attribute("aria-describedby") or "").split()
        assert pg.locator("#" + error_id).inner_text().strip()
        assert pg.locator("#" + error_id).is_visible()
    assert pg.evaluate("document.activeElement.id") == "hours" or pg.evaluate("document.activeElement.id") == "contact"

    pg.fill("#contact", "097 863 77 77")
    pg.fill("#hours", "8")
    pg.click("#send")
    pg.wait_for_selector("#done.is-on", timeout=6000)
    assert pg.get_attribute("#hours", "aria-invalid") is None
    assert pg.get_attribute("#contact", "aria-invalid") is None
    assert pg.get_attribute("#hours", "aria-describedby") is None
    assert pg.get_attribute("#contact", "aria-describedby") is None


def test_network_fallback_is_keyboard_focusable(page_factory):
    pg = page_factory(reduced=True)
    pg.route("**/api/lead", lambda route: route.abort())
    pg.fill("#subject", "Екскаватор, зміна")
    pg.fill("#contact", "097 863 77 77")
    pg.click("#send")
    pg.wait_for_selector("#fallback.is-on", timeout=6000)
    assert pg.evaluate("document.activeElement.id") == "fallback"
    assert pg.get_attribute("#fallback", "tabindex") == "-1"
    assert "Екскаватор" in pg.inner_text("#fbText")


def test_fixed_navigation_declares_scroll_space(page_factory):
    pg = page_factory(390, 844, mobile=True, reduced=True)
    metrics = pg.evaluate("""() => ({
      padding: parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop),
      margin: parseFloat(getComputedStyle(document.getElementById('tekhnika')).scrollMarginTop)
    })""")
    assert metrics["padding"] >= 70 and metrics["margin"] == metrics["padding"], metrics
