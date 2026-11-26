"""Публічна копія відрізняє архівний каталог від підтверджених умов."""
from datetime import date
import re

from playwright.sync_api import expect


def test_catalog_counts_and_estimates_keep_their_source_scope(page_factory):
    page = page_factory(reduced=True)
    data = page.evaluate(
        "({positions: PBT.fleet.length, categories: PBT.cats.length, rates: PBT.priceDate})"
    )
    archive_date = date.fromisoformat(data["rates"]).strftime("%d.%m.%Y")

    expect(page.locator(".hero__stats li").first).to_have_text(
        re.compile(rf'{data["positions"]}\s*позиції')
    )
    expect(page.locator("#tekhnika h2")).to_have_text(
        re.compile(rf'{data["positions"]} позиції\s*у {data["categories"]} категоріях')
    )
    expect(page.locator("#dokaz .fact").first).to_contain_text("позиції каталогу")

    for selector in ("#tekhnika .sec-head .lead", "#cina .calc__note", "#materialy .sec-head .lead"):
        expect(page.locator(selector)).to_contain_text(archive_date)
    expect(page.locator("#cina .calc__note")).to_contain_text("архівними ставками")
    expect(page.locator("#materialy .tile__doc").first).to_contain_text("У каталозі:")
    expect(page.locator("#materialy .mats__note")).to_contain_text("для конкретної партії")
    expect(page.locator("#cOrder")).to_have_text("Додати до заявки")


def test_route_estimate_is_labelled_historical(page_factory):
    page = page_factory(reduced=True)
    page.locator('#geoList [data-ua="Харківська"]').click()
    archive_date = date.fromisoformat(page.evaluate("PBT.priceDate")).strftime("%d.%m.%Y")
    expect(page.locator("#geoInfo .geo__src")).to_contain_text(f"Архівні ставки трала від {archive_date}")
    expect(page.locator("#geoInfo .geo__src")).to_contain_text("Актуальні умови уточнюються")
