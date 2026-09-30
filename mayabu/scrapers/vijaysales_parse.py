"""Platform-local HTML/JSON helpers for Vijay Sales (kept out of generic scraper)."""

from __future__ import annotations

from typing import Any

from mayabu.scrapers.retail_parse import (
    embedded_to_raw_record,
    extract_embedded_product_blob,
    extract_jsonld_products,
    jsonld_to_raw_record,
)

# Public category listings (/c/...) return far denser, relevant catalogs than /search?q=.
CATEGORY_PAGES: dict[str, str] = {
    "laptop": "/c/laptops",
    "notebook": "/c/laptops",
    "ultrabook": "/c/laptops",
    "macbook": "/c/laptops",
    "smartphone": "/c/mobiles",
    "mobile": "/c/mobiles",
    "iphone": "/c/mobiles",
    "phone": "/c/mobiles",
    "television": "/c/televisions",
    "tv": "/c/televisions",
    "refrigerator": "/c/refrigerators",
    "fridge": "/c/refrigerators",
    "washing": "/c/washing-machines",
    "washer": "/c/washing-machines",
    "headphones": "/c/headphones",
    "headphone": "/c/headphones",
    "earphones": "/c/earphones",
    "earphone": "/c/earphones",
    "earbuds": "/c/earphones",
    "tws": "/c/earphones",
    "neckband": "/c/neckbands",
    "camera": "/c/camera",
    "mirrorless": "/c/camera",
    "dslr": "/c/camera",
}


def resolve_vijaysales_listing_path(query: str) -> str | None:
    """Map a free-text query onto a known Vijay Sales /c/ category path."""
    q = (query or "").strip().lower()
    if not q:
        return None
    for token, path in CATEGORY_PAGES.items():
        if token in q:
            return path
    return None


def parse_vijaysales_embedded(html: str, *, base_url: str = "https://www.vijaysales.com") -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _usable(raw: dict[str, Any] | None) -> bool:
        if not raw:
            return False
        title = str(raw.get("title") or "").strip().lower()
        link = str(raw.get("link") or "").strip().lower()
        if not title or title in {"vijay sales", "vijaysales"}:
            return False
        if not link or link.rstrip("/") in {
            "https://www.vijaysales.com",
            "http://www.vijaysales.com",
            "https://vijaysales.com",
        }:
            return False
        if "/p/" not in link:
            return False
        return True

    for product in extract_jsonld_products(html):
        raw = jsonld_to_raw_record(product, base_url=base_url)
        if not _usable(raw):
            continue
        key = (raw.get("link") or raw.get("title") or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        records.append(raw)
    for product in extract_embedded_product_blob(html):
        raw = embedded_to_raw_record(product, base_url=base_url)
        if not _usable(raw):
            continue
        key = (raw.get("link") or raw.get("title") or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        records.append(raw)
    return records
