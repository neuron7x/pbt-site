#!/usr/bin/env python3
"""Fail-closed static copy checks. A pass is not proof of business performance."""
from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


class CopySurface(HTMLParser):
    """Collect rendered static text, metadata, and accessibility strings."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.jsonld_sources: list[str] = []
        self._jsonld_chunks: list[str] | None = None
        self.ignored = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = dict(attrs)
        if tag == "script":
            self.ignored += 1
            if (data.get("type") or "").lower() == "application/ld+json":
                self._jsonld_chunks = []
            return
        if tag == "style":
            self.ignored += 1
            return
        if self.ignored:
            return
        if tag == "meta" and (data.get("name") in ("description", "twitter:title", "twitter:description") or data.get("property") in ("og:title", "og:description")):
            self.parts.append(data.get("content") or "")
        for key in ("alt", "aria-label", "placeholder"):
            if data.get(key):
                self.parts.append(data[key] or "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._jsonld_chunks is not None:
            self.jsonld_sources.append("".join(self._jsonld_chunks))
            self._jsonld_chunks = None
        if tag in ("script", "style"):
            self.ignored = max(0, self.ignored - 1)

    def handle_data(self, data: str) -> None:
        if self._jsonld_chunks is not None:
            self._jsonld_chunks.append(data)
        elif not self.ignored:
            self.parts.append(data)

    @property
    def visible(self) -> str:
        return " ".join(" ".join(self.parts).split())


def _contains_key(node: object, key: str) -> bool:
    if isinstance(node, dict):
        return key in node or any(_contains_key(value, key) for value in node.values())
    if isinstance(node, list):
        return any(_contains_key(value, key) for value in node)
    return False


def verify(page: str, catalog: dict, claims: dict, terminology: dict) -> list[str]:
    errors: list[str] = []
    surface = CopySurface()
    surface.feed(page)
    text = surface.visible
    if not surface.jsonld_sources:
        errors.append("structured-data-missing")
    for source in surface.jsonld_sources:
        try:
            structured = json.loads(source)
        except json.JSONDecodeError:
            errors.append("structured-data-malformed")
            continue
        if _contains_key(structured, "areaServed"):
            errors.append("unverified-service-area-structured-data")
    if 'class="obl served"' in page:
        errors.append("map-declares-unverified-served-regions")
    if "Регіони — за запитом" not in text or "не підтверджена зона виїзду" not in text:
        errors.append("unverified-region-disclaimer-missing")
    fleet = catalog.get("fleet", [])
    categories = catalog.get("cats", [])
    all_cats = {item.get("id") for item in categories}
    used_cats = {item.get("cat") for item in fleet}

    if len(fleet) != 32 or len(all_cats) != 8 or used_cats != all_cats:
        errors.append("catalog-count-or-category-contract")
    if "32 позиції каталогу" not in text or "у 8 категоріях" not in text:
        errors.append("catalog-quantity-not-truthfully-qualified")
    if not any(i.get("cat") == "crane" and any(s.get("v") == "120 т" for s in i.get("specs", [])) for i in fleet):
        errors.append("120t-crane-is-not-grounded-in-catalog")
    if not any(i.get("cat") == "trans" and any(s.get("v") == "60 т" for s in i.get("specs", [])) for i in fleet):
        errors.append("60t-transport-is-not-grounded-in-catalog")
    if "Важкі умови." not in text or "Техніка під об’єкт." not in text:
        errors.append("industrial-hero-positioning-missing")
    if "<h1 id=\"heroTitle\"><span class=\"line\">" not in page or page.count("<h1 ") != 1:
        errors.append("semantic-hero-structure-changed")
    if "Надіслати запит" not in text or "Додати параметри до заявки" not in text:
        errors.append("user-actions-do-not-match-lead-contract")
    if "03.10.2026" not in text or "історичні" not in text or "не бронює техніку" not in text:
        errors.append("visible-pricing-or-booking-limits-missing")
    if "data-req=\"rent\"" not in page or "value=\"transport\"" not in page:
        errors.append("lead-type-contract-missing")

    forbidden = {
        "unverified-owned-fleet": r"32\s+одиниц[іьи]\b",
        "unsupported-rank": r"(?:№\s*1\b|найкращ[іаей]|лідер(?:и)?\s+ринку)",
        "unsupported-operating-hours": r"(?<!\d)24\s*/\s*7(?!\d)",
        "unsupported-absolute-sla": r"гарант(?:уємо|ований|ована)\s+виїзд",
        "old-calculator-booking-cta": r"Замовити\s+цю\s+зміну",
        "universal-material-certificates": r"на\s+кожну\s+фракцію\s+—\s+паспорт\s+якості",
        "unsupported-call-volume": r"за\s+якими\s+до\s+нас\s+дзвонять\s+найчастіше",
    }
    for rule, pattern in forbidden.items():
        if re.search(pattern, text, re.IGNORECASE):
            errors.append(f"unsubstantiated-claim:{rule}")

    if claims.get("schema_version") != 1 or terminology.get("schema_version") != 1:
        errors.append("copy-schema-version")
    records = claims.get("claims", [])
    if not isinstance(records, list) or not records:
        errors.append("missing-claim-ledger")
        records = []
    ids: set[str] = set()
    for claim in records:
        cid = claim.get("id")
        if not cid or cid in ids:
            errors.append("duplicate-or-absent-claim-id")
        ids.add(cid)
        status = claim.get("status")
        if status not in {"blocked", "source_supported"}:
            errors.append(f"{cid}:invalid-status")
        if not claim.get("owner") or not claim.get("source") or not claim.get("alternative_copy"):
            errors.append(f"{cid}:missing-evidence-owner-or-fallback")
        if status == "blocked" and (claim.get("public_copy") is not None or claim.get("verified_at") is not None):
            errors.append(f"{cid}:blocked-marked-as-public-or-verified")
        if status == "source_supported" and (not claim.get("verified_at") or claim.get("real_world_verified") is not False):
            errors.append(f"{cid}:source-confused-with-external-reality")
    if not terminology.get("preferred") or not terminology.get("avoid"):
        errors.append("terminology-not-maintained")
    return errors


def run() -> int:
    page = (ROOT / "web/index.html").read_text(encoding="utf-8")
    catalog = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
    claims = json.loads((ROOT / "copy/claim-ledger.json").read_text(encoding="utf-8"))
    terms = json.loads((ROOT / "copy/terminology.json").read_text(encoding="utf-8"))
    errors = verify(page, catalog, claims, terms)
    if errors:
        for error in errors:
            print(f"COPY_GATE FAIL: {error}", file=sys.stderr)
        return 1
    print(f"COPY_GATE PASS: {len(claims['claims'])} reviewed claim entries; source facts checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
