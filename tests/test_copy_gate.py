"""Copy claims: source-bound copy vs. blocked real-world promises."""
import copy
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from copy_gate import CopySurface, verify  # noqa: E402


def _fixtures():
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    catalog = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
    claims = json.loads((ROOT / "copy/claim-ledger.json").read_text(encoding="utf-8"))
    terms = json.loads((ROOT / "copy/terminology.json").read_text(encoding="utf-8"))
    return html, catalog, claims, terms


def test_copy_gate_accepts_current_contract():
    assert verify(*_fixtures()) == []
    proc = subprocess.run([sys.executable, "tools/copy_gate.py"], cwd=ROOT, check=False, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_static_public_copy_does_not_promote_catalog_to_owned_fleet():
    html, catalog, claims, terms = _fixtures()
    changed = html.replace("32 позиції каталогу", "32 одиниці", 1)
    failures = verify(changed, catalog, claims, terms)
    assert any("unverified-owned-fleet" in error for error in failures)


def test_drift_of_catalog_counts_fails_closed():
    html, catalog, claims, terms = _fixtures()
    altered = copy.deepcopy(catalog)
    altered["fleet"] = altered["fleet"][:-1]
    assert "catalog-count-or-category-contract" in verify(html, altered, claims, terms)


def test_blocked_claim_cannot_be_promoted_without_external_receipt():
    html, catalog, claims, terms = _fixtures()
    altered = copy.deepcopy(claims)
    target = next(entry for entry in altered["claims"] if entry["id"] == "PB-003")
    target["public_copy"] = "Поточний прайс затверджено."
    assert "PB-003:blocked-marked-as-public-or-verified" in verify(html, catalog, altered, terms)


def test_accessibility_and_metadata_strings_are_in_safety_scan():
    parser = CopySurface()
    parser.feed('<meta name="description" content="№1"><img alt="працюємо 24/7"><script>ignored</script>')
    assert "№1" in parser.visible
    assert "24/7" in parser.visible
    assert "ignored" not in parser.visible


def test_hero_cta_is_request_and_calculator_is_not_booking():
    html, _, _, _ = _fixtures()
    assert "Надіслати запит" in html
    assert "Додати параметри до заявки" in html
    assert "Замовити цю зміну" not in html
    for literal in ('name="type" value="rent"', 'name="type" value="material"', 'name="type" value="transport"', 'name="type" value="other"'):
        assert literal in html


def test_unverified_service_area_in_jsonld_is_rejected():
    html, catalog, claims, terms = _fixtures()
    altered = html.replace('"makesOffer"', '"areaServed":["Полтавська область"],"makesOffer"', 1)
    assert altered != html
    assert "unverified-service-area-structured-data" in verify(altered, catalog, claims, terms)


def test_malformed_jsonld_fails_closed():
    html, catalog, claims, terms = _fixtures()
    altered = html.replace('"@type":"LocalBusiness"', '"@type":BROKEN', 1)
    assert altered != html
    assert "structured-data-malformed" in verify(altered, catalog, claims, terms)


def test_region_map_does_not_claim_approved_dispatch():
    html, _, _, _ = _fixtures()
    script = (ROOT / "web/js/site.js").read_text(encoding="utf-8")
    assert 'class="obl served"' not in html
    assert 'class="obl inquiry"' in html
    assert "не підтверджена зона виїзду" in html
    assert "const inquiryRegions = " in script
    assert "'за запитом'" in script
    assert "'виїзд'" not in script


def test_social_metadata_is_scanned_for_unsupported_superlatives():
    html, catalog, claims, terms = _fixtures()
    altered = html.replace('property="og:title" content="ПЛЕЙНБУД"', 'property="og:title" content="№1"', 1)
    assert altered != html
    assert "unsubstantiated-claim:unsupported-rank" in verify(altered, catalog, claims, terms)
