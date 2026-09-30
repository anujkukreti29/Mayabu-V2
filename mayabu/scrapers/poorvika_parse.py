"""Platform-local HTML helpers for Poorvika (dedupe noisy duplicate anchors)."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse, urlunparse

from mayabu.scrapers.retail_parse import (
    embedded_to_raw_record,
    extract_embedded_product_blob,
    extract_jsonld_products,
    jsonld_to_raw_record,
    price_to_int,
)

_PRODUCT_PATH_RE = re.compile(r"/p(?:/|$|\?)", re.I)
_CARD_RE = re.compile(
    r'<div[^>]*class=["\'][^"\']*product-card[^"\']*["\'][^>]*>(.*?)</div>',
    re.I | re.S,
)
_HREF_RE = re.compile(r'href=["\']([^"\']+/p(?:/|\?|#|["\']))', re.I)
_TITLE_RE = re.compile(
    r'(?:title=["\']([^"\']+)["\']|<h[1-4][^>]*>\s*([^<]+)\s*</h[1-4]>)',
    re.I,
)
_SELLING_PRICE_RE = re.compile(
    r'class=["\'][^"\']*selling-price[^"\']*["\'][^>]*>\s*([^<]+)',
    re.I,
)
_MRP_RE = re.compile(
    r'class=["\'][^"\']*mrp[^"\']*["\'][^>]*>\s*([^<]+)',
    re.I,
)
_IMG_RE = re.compile(
    r'<img[^>]+(?:data-src|src)=["\']([^"\']+)["\']',
    re.I,
)

# Public category landing pages that reliably load PIM product group JSON.
CATEGORY_PAGES: dict[str, str] = {
    "laptop": "/laptops/page",
    "notebook": "/laptops/page",
    "ultrabook": "/laptops/page",
    "macbook": "/laptops/page",
    "smartphone": "/mobile-and-accessories/page",
    "mobile": "/mobile-and-accessories/page",
    "iphone": "/mobile-and-accessories/page",
    "phone": "/mobile-and-accessories/page",
    "television": "/tv-audio/page",
    "tv": "/tv-audio/page",
    "refrigerator": "/home-appliances/page",
    "fridge": "/home-appliances/page",
    "washing": "/home-appliances/page",
    "washer": "/home-appliances/page",
    "headphones": "/tv-audio/page",
    "earbuds": "/tv-audio/page",
    "tws": "/tv-audio/page",
    "camera": "/smart-technology/page",
}


def resolve_poorvika_listing_path(query: str) -> str | None:
    """Map a free-text query onto a known Poorvika category landing path."""
    q = (query or "").strip().lower()
    if not q:
        return None
    for token, path in CATEGORY_PAGES.items():
        if token in q:
            return path
    return None


def canonicalize_poorvika_url(url: str) -> str:
    """Stable product path without tracking query params."""
    if not url:
        return ""
    parsed = urlparse(url)
    path = re.sub(r"/+$", "", parsed.path or "")
    return urlunparse((parsed.scheme or "https", parsed.netloc, path, "", "", ""))


def _pim_selling_price(item: dict[str, Any]) -> int | None:
    direct = price_to_int(
        item.get("price")
        or item.get("selling_price")
        or item.get("special_price")
        or item.get("offer_price")
    )
    if direct is not None:
        return direct
    prices = item.get("prices")
    if isinstance(prices, list):
        candidates: list[int] = []
        for block in prices:
            if not isinstance(block, dict):
                continue
            for sp in block.get("sp") or []:
                if isinstance(sp, dict):
                    parsed = price_to_int(sp.get("price"))
                    if parsed is not None:
                        candidates.append(parsed)
        if candidates:
            # Prefer the latest/lowest current selling price entry if multiple.
            return min(candidates)
    return None


def _pim_mrp(item: dict[str, Any]) -> int | None:
    direct = price_to_int(item.get("mrp") or item.get("max_retail_price"))
    if direct is not None:
        return direct
    mrp = item.get("mrp")
    if isinstance(mrp, list):
        for block in mrp:
            if isinstance(block, dict):
                parsed = price_to_int(block.get("price") or block.get("mrp") or block.get("amount"))
                if parsed is not None:
                    return parsed
            else:
                parsed = price_to_int(block)
                if parsed is not None:
                    return parsed
    return None


def records_from_pim_group_payload(
    payload: Any, *, base_url: str = "https://www.poorvika.com"
) -> list[dict[str, Any]]:
    """Convert Poorvika PIM page/groups/group JSON into discovery raw records."""
    data = payload
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except Exception:
            return []
    if not isinstance(data, dict):
        return []
    items = data.get("data")
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("name") or item.get("title")
        code = item.get("code") or item.get("sku") or item.get("slug") or item.get("id")
        if not title:
            continue
        key = str(code or title).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        price = _pim_selling_price(item)
        mrp = _pim_mrp(item)
        image = item.get("image") or item.get("image_url") or item.get("thumb") or item.get("thumbnail")
        if isinstance(image, dict):
            image = image.get("url")
        link = ""
        if code:
            link = f"{base_url.rstrip('/')}/{str(code).strip().strip('/')}/p"
        out.append(
            {
                "title": str(title).strip(),
                "currentPrice": str(price) if price is not None else "N/A",
                "maxRetailPrice": str(mrp) if mrp is not None else "N/A",
                "discount": None,
                "link": link,
                "image": str(image or ""),
                "sku": item.get("item_code") or code,
            }
        )
    return out


def _abs(base_url: str, href: str) -> str:
    href = (href or "").strip()
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return f"{base_url.rstrip('/')}/{href.lstrip('/')}"


def records_from_poorvika_html_cards(
    html: str, *, base_url: str = "https://www.poorvika.com"
) -> list[dict[str, Any]]:
    """Parse product-card markup; one logical product → one record (dedupe by /p path)."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    cards = _CARD_RE.findall(html or "")
    # Fallback: scan whole page for /p anchors when card wrappers are absent.
    scopes = cards if cards else [html or ""]
    for scope in scopes:
        href_match = _HREF_RE.search(scope)
        if not href_match:
            continue
        href = href_match.group(1).rstrip("\"'")
        link = canonicalize_poorvika_url(_abs(base_url, href))
        key = link.lower()
        if not key or key in seen:
            continue
        if not _PRODUCT_PATH_RE.search(link):
            continue
        title = ""
        title_match = _TITLE_RE.search(scope)
        if title_match:
            title = (title_match.group(1) or title_match.group(2) or "").strip()
        if not title or title.lower() in {"view", "quick view", "buy now"}:
            # Prefer the first meaningful anchor title attribute on this card.
            for m in re.finditer(r'title=["\']([^"\']{8,})["\']', scope, re.I):
                candidate = m.group(1).strip()
                if candidate.lower() not in {"view", "quick view"}:
                    title = candidate
                    break
        if not title or len(title) < 5:
            continue
        price_text = ""
        pm = _SELLING_PRICE_RE.search(scope)
        if pm:
            price_text = pm.group(1).strip()
        mrp_text = ""
        mm = _MRP_RE.search(scope)
        if mm:
            mrp_text = mm.group(1).strip()
        image = ""
        im = _IMG_RE.search(scope)
        if im:
            image = _abs(base_url, im.group(1).strip())
        price = price_to_int(price_text)
        mrp = price_to_int(mrp_text)
        seen.add(key)
        out.append(
            {
                "title": title[:300],
                "currentPrice": str(price) if price is not None else "N/A",
                "maxRetailPrice": str(mrp) if mrp is not None else "N/A",
                "discount": None,
                "link": link,
                "image": image,
            }
        )
    return out


def parse_poorvika_embedded(html: str, *, base_url: str = "https://www.poorvika.com") -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(raw: dict[str, Any] | None) -> None:
        if not raw:
            return
        link = canonicalize_poorvika_url(str(raw.get("link") or ""))
        title = str(raw.get("title") or "").strip().lower()
        key = link.lower() or title
        if not key or key in seen:
            return
        # Allow PIM-derived /code/p links and classic /p paths.
        if link and not (_PRODUCT_PATH_RE.search(link) or link.rstrip("/").endswith("/p")):
            return
        # Reject nav category labels mistaken for products.
        if title in {
            "mobiles & accessories",
            "computers & tablets",
            "kitchen appliances",
            "smart technology",
            "home appliances",
            "tv & audio",
        }:
            return
        raw["link"] = link or raw.get("link")
        price = price_to_int(raw.get("currentPrice"))
        raw["currentPrice"] = str(price) if price is not None else "N/A"
        seen.add(key)
        records.append(raw)

    for product in extract_jsonld_products(html):
        _add(jsonld_to_raw_record(product, base_url=base_url))
    for product in extract_embedded_product_blob(html):
        _add(embedded_to_raw_record(product, base_url=base_url))
    for raw in records_from_poorvika_html_cards(html, base_url=base_url):
        _add(raw)
    return records
