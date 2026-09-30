"""Platform-local HTML/JSON helpers for JioMart public browser-delivered data."""

from __future__ import annotations

import json
import re
from typing import Any

from mayabu.scrapers.retail_parse import (
    embedded_to_raw_record,
    extract_embedded_product_blob,
    extract_jsonld_products,
    html_looks_blocked,
    jsonld_to_raw_record,
)

_NEXT_DATA_RE = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)


def _walk_products(node: Any, out: list[dict[str, Any]], *, depth: int = 0) -> None:
    if depth > 12 or len(out) >= 100:
        return
    if isinstance(node, list):
        for item in node[:200]:
            _walk_products(item, out, depth=depth + 1)
        return
    if not isinstance(node, dict):
        return
    keys = {str(k).lower() for k in node.keys()}
    title = node.get("name") or node.get("title") or node.get("product_name") or node.get("display_name")
    if title and (
        "price" in keys
        or "mrp" in keys
        or "selling_price" in keys
        or "offer_price" in keys
        or "image_url" in keys
        or "product_code" in keys
    ):
        out.append(node)
    for value in list(node.values())[:40]:
        if isinstance(value, (dict, list)):
            _walk_products(value, out, depth=depth + 1)


def parse_jiomart_embedded(html: str, *, base_url: str = "https://www.jiomart.com") -> list[dict[str, Any]]:
    """Extract products from JSON-LD / __NEXT_DATA__ / hydration when publicly present."""
    if html_looks_blocked(html):
        return []
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(raw: dict[str, Any] | None) -> None:
        if not raw:
            return
        title = str(raw.get("title") or "").strip()
        link = str(raw.get("link") or "")
        title_l = title.lower()
        if not title or len(title) < 8:
            return
        if any(
            junk in title_l
            for junk in (
                "order listing",
                "my orders",
                "hellcat",
                "login",
                "sign in",
                "terms & conditions",
                "privacy policy",
            )
        ):
            return
        if link and "/p/" not in link and "/product/" not in link:
            return
        key = (link or title).lower()
        if not key or key in seen:
            return
        seen.add(key)
        records.append(raw)

    for product in extract_jsonld_products(html):
        _add(jsonld_to_raw_record(product, base_url=base_url))

    next_match = _NEXT_DATA_RE.search(html or "")
    if next_match:
        try:
            payload = json.loads(next_match.group(1))
        except Exception:
            payload = None
        found: list[dict[str, Any]] = []
        if payload is not None:
            _walk_products(payload, found)
        for product in found:
            normalized = {
                **product,
                "name": product.get("name")
                or product.get("title")
                or product.get("product_name")
                or product.get("display_name"),
                "price": product.get("price")
                or product.get("selling_price")
                or product.get("offer_price")
                or product.get("final_price"),
                "mrp": product.get("mrp") or product.get("max_retail_price"),
                "url": product.get("url")
                or product.get("product_url")
                or product.get("share_url"),
                "image": product.get("image")
                or product.get("image_url")
                or product.get("image_path"),
                "sku": product.get("sku")
                or product.get("product_code")
                or product.get("variant_id")
                or product.get("id"),
            }
            _add(embedded_to_raw_record(normalized, base_url=base_url))

    for product in extract_embedded_product_blob(html):
        _add(embedded_to_raw_record(product, base_url=base_url))
    return records
