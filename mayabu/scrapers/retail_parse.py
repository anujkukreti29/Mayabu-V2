"""Pure HTML/JSON-LD parsing helpers shared by discovery and refresh (no Playwright)."""

from __future__ import annotations

import html as html_lib
import json
import re
import urllib.parse
from typing import Any

from mayabu.domain.categories.registry import price_bounds_for

BLOCKED_MARKERS = (
    "captcha",
    "robot check",
    "unusual traffic",
    "access denied",
    "verify you are human",
    "please verify",
    "cf-challenge",
    "attention required",
)

PRICE_TEXT_RE = re.compile(
    r"(?:₹|Rs\.?|INR)?\s*"
    r"([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.\d{1,2})?|[0-9]{3,7}(?:\.\d{1,2})?)",
    re.I,
)

_PRICE_NOISE_RE = re.compile(
    r"("
    r"\bemi\b|"
    r"/\s*month|"
    r"per\s+month|"
    r"monthly|"
    r"\bcashback\b|"
    r"\bexchange\b|"
    r"\bcoupon\b|"
    r"\bbank\s+offer\b|"
    r"\bdelivery\b|"
    r"\bwarranty\b|"
    r"\bstarting\s+(?:at|from)\b"
    r")",
    re.I,
)

_OG_PRICE_RE = re.compile(
    r'<meta[^>]+property=["\']product:price:amount["\'][^>]+content=["\']([^"\']+)["\']',
    re.I,
)
_OG_MRP_RE = re.compile(
    r'<meta[^>]+property=["\']product:original_price:amount["\'][^>]+content=["\']([^"\']+)["\']',
    re.I,
)
_ITEM_PRICE_RE = re.compile(
    r'itemprop=["\']price["\'][^>]*content=["\']([^"\']+)["\']',
    re.I,
)


def decode_text(value: str | None) -> str:
    if not value:
        return ""
    text = html_lib.unescape(str(value))
    for old, new in {
        "\\u002F": "/",
        "\\/": "/",
        "\\u20b9": "₹",
        "&nbsp;": " ",
        "&#8377;": "₹",
    }.items():
        text = text.replace(old, new)
    return text


def price_to_int(value: Any, *, min_value: int = 100, max_value: int = 2_000_000) -> int | None:
    if value is None:
        return None
    text = decode_text(str(value))
    # Card blobs often concatenate selling price + EMI/offer lines. Prefer the
    # first currency amount that appears before noise segments.
    segments = re.split(r"[\n|;]+", text)
    primary = segments[0].strip() if segments else text
    if _PRICE_NOISE_RE.search(primary):
        # Entire first segment is EMI-only — reject (do not invent selling price).
        return None
    # If later segments mention EMI but the first line has a clean price, use it.
    match = PRICE_TEXT_RE.search(primary)
    if not match and not _PRICE_NOISE_RE.search(text):
        match = PRICE_TEXT_RE.search(text)
    if not match:
        if _PRICE_NOISE_RE.search(text):
            return None
        digits = re.sub(r"[^\d]", "", text)
        if not digits:
            return None
        try:
            price = int(digits)
        except ValueError:
            return None
    else:
        raw = re.sub(r"\.\d{1,2}$", "", match.group(1).strip())
        digits = re.sub(r"[^\d]", "", raw)
        if not digits:
            return None
        try:
            price = int(digits)
        except ValueError:
            return None
    if price < min_value or price > max_value:
        return None
    return price


def extract_embedded_product_blob(html: str) -> list[dict[str, Any]]:
    """Best-effort extraction of product-like dicts from script/hydration JSON.

    Conservative: only returns objects that look like products (name/title + price/url).
    """
    products: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in re.finditer(
        r"<script[^>]*>(.*?)</script>",
        html or "",
        flags=re.I | re.S,
    ):
        raw = match.group(1)
        if not raw or len(raw) < 40:
            continue
        if "price" not in raw.lower() and "product" not in raw.lower():
            continue
        # Prefer JSON.parse payloads and Next/__NEXT_DATA__ style blobs.
        for candidate in re.finditer(r"(\{[^{}]{0,2000}\"[^\"]*(?:name|title|productName)\"[^{}]{0,4000}\})", raw):
            blob = candidate.group(1)
            try:
                data = json.loads(blob)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            title = data.get("name") or data.get("title") or data.get("productName")
            if not title:
                continue
            key = str(title).strip().lower()
            if key in seen:
                continue
            seen.add(key)
            products.append(data)
            if len(products) >= 80:
                return products
    return products


def embedded_to_raw_record(product: dict[str, Any], *, base_url: str) -> dict[str, Any] | None:
    title = product.get("name") or product.get("title") or product.get("productName")
    if not title:
        return None
    price = price_to_int(
        product.get("price")
        or product.get("sellingPrice")
        or product.get("offerPrice")
        or product.get("finalPrice")
        or product.get("sale_price")
    )
    mrp = price_to_int(
        product.get("mrp")
        or product.get("maxRetailPrice")
        or product.get("listPrice")
        or product.get("wasPrice")
    )
    url = abs_url(
        base_url,
        product.get("url")
        or product.get("productUrl")
        or product.get("canonicalUrl")
        or product.get("link")
        or product.get("@id"),
    )
    image = product.get("image") or product.get("imageUrl") or product.get("thumbnail")
    if isinstance(image, list) and image:
        image = image[0]
    if isinstance(image, dict):
        image = image.get("url")
    return {
        "title": str(title).strip(),
        "currentPrice": str(price) if price is not None else "N/A",
        "maxRetailPrice": str(mrp) if mrp is not None else "N/A",
        "discount": None,
        "link": url,
        "image": abs_url(base_url, str(image) if image else ""),
        "sku": product.get("sku")
        or product.get("productId")
        or product.get("id")
        or product.get("nativeId"),
    }


def abs_url(base: str, url: str | None) -> str:
    if not url:
        return ""
    text = decode_text(url).strip()
    if text.startswith("//"):
        return "https:" + text
    if text.startswith("http"):
        return text.split("#", 1)[0]
    return urllib.parse.urljoin(base.rstrip("/") + "/", text.lstrip("/")).split("#", 1)[0]


def html_looks_blocked(html: str, title: str = "") -> bool:
    blob = (html or "")[:80_000].lower() + " " + (title or "").lower()
    return any(marker in blob for marker in BLOCKED_MARKERS)


def extract_jsonld_products(html: str) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html or "",
        flags=re.I | re.S,
    ):
        raw = match.group(1).strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                stack.extend(item)
                continue
            if not isinstance(item, dict):
                continue
            if "@graph" in item and isinstance(item["@graph"], list):
                stack.extend(item["@graph"])
            # ItemList / search result collections
            elements = item.get("itemListElement")
            if isinstance(elements, list):
                for entry in elements:
                    if isinstance(entry, dict):
                        nested = entry.get("item") if isinstance(entry.get("item"), dict) else entry
                        stack.append(nested)
            types = item.get("@type")
            type_names = (
                [types]
                if isinstance(types, str)
                else [t for t in types]
                if isinstance(types, list)
                else []
            )
            lowered = {str(t).lower() for t in type_names}
            if "product" in lowered:
                products.append(item)
    return products


def jsonld_to_raw_record(product: dict[str, Any], *, base_url: str) -> dict[str, Any] | None:
    title = product.get("name") or product.get("title")
    if not title:
        return None
    offer = product.get("offers")
    if isinstance(offer, list) and offer:
        offer = offer[0]
    if not isinstance(offer, dict):
        offer = {}
    price = price_to_int(offer.get("price") or product.get("price"))
    mrp = price_to_int(offer.get("highPrice") or product.get("mrp"))
    url = abs_url(base_url, product.get("url") or product.get("@id"))
    image = product.get("image")
    if isinstance(image, list) and image:
        image = image[0]
    if isinstance(image, dict):
        image = image.get("url")
    image_url = abs_url(base_url, str(image) if image else "")
    return {
        "title": str(title).strip(),
        "currentPrice": str(price) if price is not None else "N/A",
        "maxRetailPrice": str(mrp) if mrp is not None else "N/A",
        "discount": None,
        "link": url,
        "image": image_url,
        "sku": product.get("sku") or product.get("mpn") or product.get("productID"),
    }


def extract_refresh_from_html(html: str, *, category: str | None = None) -> tuple[int | None, int | None]:
    lo, hi = price_bounds_for(category or "laptop")
    current = None
    mrp = None

    for product in extract_jsonld_products(html):
        offer = product.get("offers")
        if isinstance(offer, list) and offer:
            offer = offer[0]
        if not isinstance(offer, dict):
            offer = {}
        current = price_to_int(offer.get("price") or product.get("price"), min_value=lo, max_value=hi)
        mrp = price_to_int(offer.get("highPrice") or product.get("mrp"), min_value=lo, max_value=hi)
        if current is not None:
            break

    if current is None:
        og = _OG_PRICE_RE.search(html or "")
        if og:
            current = price_to_int(og.group(1), min_value=lo, max_value=hi)
    if mrp is None:
        ogm = _OG_MRP_RE.search(html or "")
        if ogm:
            mrp = price_to_int(ogm.group(1), min_value=lo, max_value=hi)
    if current is None:
        ip = _ITEM_PRICE_RE.search(html or "")
        if ip:
            current = price_to_int(ip.group(1), min_value=lo, max_value=hi)

    if mrp is not None and current is not None and mrp < current:
        mrp = None
    return current, mrp
