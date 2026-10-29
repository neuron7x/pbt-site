"""Issue #4: одна семантика CSS-токенів, жодного прихованого шару теми."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_all_semantic_component_tokens_exist_for_both_themes():
    css = (ROOT / "web" / "css" / "site.css").read_text(encoding="utf-8")
    sky_start = css.index(':root[data-theme="sky"]')
    precision_start = css.index(':root[data-theme="precision"]')
    components_start = css.index("*,*::before")
    sky, precision, components = (
        css[sky_start:precision_start],
        css[precision_start:components_start],
        css[components_start:],
    )
    pattern = r"--(t-[a-z][a-z0-9-]+)\s*:"
    sky_names = re.findall(pattern, sky)
    precision_names = re.findall(pattern, precision)
    assert len(sky_names) == len(set(sky_names))
    assert len(precision_names) == len(set(precision_names))
    assert set(sky_names) == set(precision_names)
    assert len(sky_names) >= 95
    uses = set(re.findall(r"var\(--(t-[a-z][a-z0-9-]+)", components))
    assert uses <= set(sky_names), sorted(uses - set(sky_names))
    # Різні компоненти не обираються селектором теми; варіюються лише значення.
    assert not re.search(r'\[data-theme\s*=\s*["\']?(?:sky|precision)["\']?\]\s+[.#]', components)


def test_theme_selection_is_prepaint_and_does_not_add_a_css_layer():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "web" / "css" / "site.css").read_text(encoding="utf-8")
    assert html.index("localStorage.getItem('pbt-theme')") < html.index('href="css/site.css"')
    assert html.count('rel="stylesheet"') == 2  # fonts.css + site.css
    assert "css/precision.css" not in html
    assert not (ROOT / "web" / "css" / "precision.css").exists()
    assert "cdn." not in css and "@import" not in css
