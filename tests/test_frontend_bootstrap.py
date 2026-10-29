"""Fail-fast: bootstrap не повинен падати до ініціалізації каталогу й форми."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_single_element_query_never_has_array_iteration():
    source = (ROOT / "web" / "js" / "site.js").read_text(encoding="utf-8")
    # $() повертає Element, лише $$() повертає масив.
    assert not re.findall(r"(?<!\$)\$\([^\n)]*\)\.forEach\(", source)


def test_frontend_bootstrap_initializes_all_public_controls(page_factory):
    page = page_factory(reduced=True)
    assert page.evaluate("typeof window.PBTv") == "function"
    assert page.evaluate("typeof window.PBTcalc") == "function"
    assert page.locator("#park .unit").count() == 32
    assert page.locator("#chips .chip").count() == 9
    assert page.locator("#cine .cine__ch").count() == 6
    assert not [error for error in page.errors if "favicon" not in error]
