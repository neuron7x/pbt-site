"""WCAG 2.2 AA: мобільне меню кероване з клавіатури й не пропускає фокус на фон."""


def test_mobile_menu_exposes_modal_semantics_and_return_focus(page_factory):
    pg = page_factory(390, 844, mobile=True, reduced=True)
    pg.click(".burger")
    assert pg.get_attribute("#menu", "role") == "dialog"
    assert pg.get_attribute("#menu", "aria-modal") == "true"
    assert pg.get_attribute(".burger", "aria-expanded") == "true"
    assert pg.evaluate("document.querySelector('#main').inert && document.querySelector('.foot').inert && document.querySelector('#nav').inert")
    assert pg.evaluate("document.activeElement.id") == "menuClose"
    size = pg.locator("#menuClose").bounding_box()
    assert size["width"] >= 44 and size["height"] >= 44

    pg.keyboard.press("Shift+Tab")
    assert pg.evaluate("document.activeElement.closest('#menu') !== null")
    assert pg.evaluate("document.activeElement.tagName") == "A"
    pg.keyboard.press("Tab")
    assert pg.evaluate("document.activeElement.id") == "menuClose"

    pg.keyboard.press("Escape")
    assert pg.locator("#menu").is_hidden()
    assert pg.evaluate("document.activeElement.classList.contains('burger')")
    assert pg.get_attribute(".burger", "aria-expanded") == "false"
    assert pg.evaluate("!document.querySelector('#main').inert && !document.querySelector('.foot').inert && !document.querySelector('#nav').inert")
    assert pg.evaluate("document.body.style.overflow") == ""


def test_menu_link_closes_dialog_and_focuses_destination(page_factory):
    pg = page_factory(390, 844, mobile=True, reduced=True)
    pg.click(".burger")
    pg.click('#menu a[href="#tekhnika"]')
    pg.wait_for_timeout(100)
    assert pg.locator("#menu").is_hidden()
    assert pg.evaluate("document.activeElement.id") == "tekhnika"
    assert pg.evaluate("!document.getElementById('main').inert")


def test_menu_closes_if_viewport_changes_to_desktop(page_factory):
    pg = page_factory(390, 844, mobile=True)
    pg.click(".burger")
    pg.set_viewport_size({"width": 1280, "height": 800})
    pg.wait_for_timeout(300)
    assert pg.locator("#menu").is_hidden()
    assert pg.evaluate("!document.querySelector('#nav').inert")
