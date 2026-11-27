"""Каталог пояснює параметри й запит ціни без публікації старих ставок."""
import re

from playwright.sync_api import expect


def test_catalog_preserves_counts_and_discloses_contractual_pricing(page_factory):
    page = page_factory(reduced=True)
    data = page.evaluate("({positions: PBT.fleet.length, categories: PBT.cats.length, hasRates: Object.prototype.hasOwnProperty.call(PBT, 'priceDate')})")
    assert data["hasRates"] is False

    expect(page.locator(".hero__stats li").first).to_have_text(
        re.compile(rf'{data["positions"]}\s*позиції')
    )
    expect(page.locator("#tekhnika h2")).to_have_text(
        re.compile(rf'{data["positions"]} позиції\s*у {data["categories"]} категоріях')
    )
    expect(page.locator("#dokaz .fact").first).to_contain_text("позиції каталогу")
    expect(page.locator("#materialy .tile__doc").first).to_contain_text("У каталозі:")
    expect(page.locator("#materialy .mats__note")).to_contain_text("для конкретної партії")
    assert not re.search(r"\d[\d\s.,]*грн", page.locator("main").inner_text(), re.IGNORECASE)


def test_route_preserves_reference_distance_without_publishable_tariff(page_factory):
    page = page_factory(reduced=True)
    page.locator('#geoList [data-ua="Харківська"]').click()
    panel = page.locator("#geoInfo")
    expected = page.evaluate("PBT.routes.to['Харківська'].km")
    expect(panel).to_contain_text(f"{expected} км")
    assert "грн" not in panel.inner_text().lower()
