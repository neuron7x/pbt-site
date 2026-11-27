"""Публічна заявка зберігає технічні факти для уточнення подачі."""

import pytest


@pytest.mark.parametrize("ident,known_mass", [("e-1", True), ("e-3", True),
                                              ("b-4", True), ("nav-1", False)])
def test_intake_preserves_documented_mass_without_deriving_delivery(page_factory, ident, known_mass):
    page = page_factory(reduced=True)
    assert page.locator("#cKind").count() == 1
    result = page.evaluate(r"""id => {
      const unit = PBT.fleet.find(item => item.id === id);
      return {
        knownMass: unit.specs.some(spec => /^маса/i.test(spec.k) && /\d/.test(spec.v)),
        publicPrice: Object.prototype.hasOwnProperty.call(unit, 'price'),
      };
    }""", ident)
    assert result == {"knownMass": known_mass, "publicPrice": False}
    assert page.locator("#cKmN, #cOut[data-estimate], #cOut[data-total]").count() == 0
