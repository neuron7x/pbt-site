"""Калькулятор: жодної вигаданої маси чи підтвердженої ціни подачі."""

import pytest


@pytest.mark.parametrize("ident,hours,km,expected", [
    ("e-1", 10, 20, 10 * 1350 + 20 * 100),  # JCB JS220: маса 22 т, трал 40 т
    ("e-3", 1, 10, 1500 + 10 * 100),        # DX300: маса 31 т, трал 40 т
    ("b-4", 2, 10, 2 * 1600 + 10 * 100),    # бульдозер: маса 15 т
    ("nav-1", 2, 10, None),                 # навантажувач: масу не вказано
    ("nav-1", 2, 0, 2 * 1400),             # лише оренда, подачу не заявлено
    ("ak-1", 2, 10, 2 * 1800),             # кран їде сам; доставка окремо
])
def test_calculator_never_assumes_unknown_equipment_mass(page_factory, ident, hours, km, expected):
    pg = page_factory(reduced=True)
    actual = pg.evaluate("([id, h, km]) => window.PBTcalc(id, h, km)", [ident, hours, km])
    assert actual == expected


def test_missing_mass_shows_rental_only_and_no_complete_estimate(page_factory):
    pg = page_factory(reduced=True)
    pg.select_option("#cMachine", "nav-1")
    pg.fill("#cHoursN", "2")
    pg.dispatch_event("#cHoursN", "input")
    pg.fill("#cKmN", "10")
    pg.dispatch_event("#cKmN", "input")
    total = pg.locator("#cOut")
    assert total.get_attribute("data-estimate") == "rent-only"
    assert total.get_attribute("data-total") == ""
    text = pg.locator("#cLines").inner_text().lower()
    assert "маса невідома" in text
    assert "оренда без подачі" in text
    assert "".join(filter(str.isdigit, pg.inner_text("#cTotal"))) == "2800", text
    assert "ціну уточнити" in pg.get_attribute("#cOrder", "data-subject")


def test_crane_cost_is_presented_as_rental_without_delivery(page_factory):
    pg = page_factory(reduced=True)
    pg.select_option("#cMachine", "ak-1")
    assert pg.get_attribute("#cOut", "data-estimate") == "rent-only"
    assert pg.get_attribute("#cOut", "data-total") == ""
    assert "Подача автокрана" in pg.inner_text("#cLines")
    assert pg.is_disabled("#cKmN")


def test_no_available_trailer_fails_closed(page_factory):
    pg = page_factory(reduced=True)
    result = pg.evaluate("""() => {
      const u = window.PBT.fleet.find(x => x.id === 'e-1');
      const prev = u.specs;
      try {
        u.specs = [{k: 'Маса', v: '80 т'}];
        return window.PBTcalc('e-1', 2, 30);
      } finally { u.specs = prev; }
    }""")
    assert result is None


@pytest.mark.parametrize("hours,km", [(0, 1), (1, -1), (5001, 5), (1.5, 2), (1, 3001)])
def test_invalid_calculator_inputs_fail_closed(page_factory, hours, km):
    pg = page_factory(reduced=True)
    assert pg.evaluate("([hours, km]) => window.PBTcalc('e-1', hours, km)", [hours, km]) is None
