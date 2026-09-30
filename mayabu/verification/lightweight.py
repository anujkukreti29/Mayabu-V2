"""Low-cost product-page verification before Playwright fallback.

The lightweight path reads a bounded amount of HTML and extracts structured
metadata. It intentionally falls back to the existing browser scraper whenever
confidence is insufficient or the platform blocks plain HTTP requests.
"""

from __future__ import annotations

import asyncio
import json
import re
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mayabu_refresh.common import (
    DEFAULT_USER_AGENT,
    calculate_discount_percent,
    clean_plain_price_to_int,
    validate_platform_url,
)
from mayabu_refresh.models import RefreshResult

_MAX_HTML_BYTES = 2_000_000
_JSON_LD_RE = re.compile(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.I | re.S)
_META_RE = re.compile(r"<meta\s+[^>]*(?:property|itemprop|name)=[\"']([^\"']+)[\"'][^>]*content=[\"']([^\"']*)[\"'][^>]*>", re.I)
_PRICE_PATTERNS = (
    re.compile(r'"price"\s*:\s*"?([0-9][0-9,]*(?:\.[0-9]{1,2})?)"?', re.I),
    re.compile(r'"lowPrice"\s*:\s*"?([0-9][0-9,]*(?:\.[0-9]{1,2})?)"?', re.I),
)
_MRP_PATTERNS = (
    re.compile(r'"mrp"\s*:\s*"?([0-9][0-9,]*(?:\.[0-9]{1,2})?)"?', re.I),
    re.compile(r'"listPrice"\s*:\s*"?([0-9][0-9,]*(?:\.[0-9]{1,2})?)"?', re.I),
)


def _stock_status(text: str) -> str:
    from mayabu_refresh.stock import classify_stock_text

    return classify_stock_text(text, scoped=False).public_stock



def _first_price(patterns: tuple[re.Pattern[str], ...], text: str) -> int | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            price = clean_plain_price_to_int(match.group(1))
            if price is not None:
                return price
    return None


def _extract_from_json_ld(html: str) -> tuple[int | None, int | None, str]:
    price = None
    mrp = None
    stock = "unknown"
    for raw in _JSON_LD_RE.findall(html):
        stock = _stock_status(raw) if stock == "unknown" else stock
        try:
            payload = json.loads(unescape(raw).strip())
        except Exception:
            price = price or _first_price(_PRICE_PATTERNS, raw)
            mrp = mrp or _first_price(_MRP_PATTERNS, raw)
            continue
        stack = payload if isinstance(payload, list) else [payload]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
                continue
            if not isinstance(node, dict):
                continue
            stack.extend(value for value in node.values() if isinstance(value, (dict, list)))
            if price is None and node.get("price") is not None:
                price = clean_plain_price_to_int(node.get("price"))
            if mrp is None:
                for key in ("mrp", "listPrice", "highPrice"):
                    if node.get(key) is not None:
                        mrp = clean_plain_price_to_int(node.get(key))
                        if mrp:
                            break
            availability = str(node.get("availability") or "")
            if availability:
                stock = _stock_status(availability)
    return price, mrp, stock


def _extract_meta(html: str) -> tuple[int | None, int | None, str]:
    values = {key.lower(): unescape(value) for key, value in _META_RE.findall(html)}
    price = None
    for key in ("product:price:amount", "price", "og:price:amount"):
        if key in values:
            price = clean_plain_price_to_int(values[key])
            if price:
                break
    mrp = None
    for key in ("product:original_price:amount", "mrp", "listprice"):
        if key in values:
            mrp = clean_plain_price_to_int(values[key])
            if mrp:
                break
    stock = _stock_status(" ".join(values.get(key, "") for key in ("availability", "product:availability")))
    return price, mrp, stock


def _fetch(platform: str, url: str, timeout_seconds: float) -> RefreshResult:
    if not validate_platform_url(platform, url):
        return RefreshResult.failed("lightweight_invalid_platform_url")
    request = Request(
        url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-IN,en;q=0.9",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            final_url = response.geturl()
            if not validate_platform_url(platform, final_url):
                return RefreshResult.failed("lightweight_cross_domain_redirect")
            status = int(getattr(response, "status", 200) or 200)
            if status >= 400:
                return RefreshResult.failed(f"lightweight_http_{status}")
            html = response.read(_MAX_HTML_BYTES + 1)
    except HTTPError as exc:
        return RefreshResult.failed(f"lightweight_http_{exc.code}", "blocked" if exc.code in {403, 429} else "failed")
    except (URLError, TimeoutError, OSError) as exc:
        return RefreshResult.failed(f"lightweight_network_error:{type(exc).__name__}")

    if len(html) > _MAX_HTML_BYTES:
        return RefreshResult.failed("lightweight_response_too_large")
    text = html.decode("utf-8", errors="ignore")
    lowered = text.lower()
    if any(token in lowered for token in ("captcha", "robot check", "verify you are human", "unusual traffic")):
        return RefreshResult.failed("lightweight_blocked_or_captcha", "captcha")

    json_price, json_mrp, json_stock = _extract_from_json_ld(text)
    meta_price, meta_mrp, meta_stock = _extract_meta(text)
    price = json_price or meta_price or _first_price(_PRICE_PATTERNS, text)
    mrp = json_mrp or meta_mrp or _first_price(_MRP_PATTERNS, text)
    stock = json_stock if json_stock != "unknown" else meta_stock
    if stock == "unknown":
        from mayabu_refresh.stock import classify_stock_text

        classified = classify_stock_text(lowered, scoped=False)
        stock = classified.public_stock
        stock_reason = classified.reason
        stock_confidence = classified.confidence
    else:
        stock_reason = "jsonld_or_meta"
        stock_confidence = "medium"
    if price is None and stock != "out_of_stock":
        return RefreshResult.failed("lightweight_price_not_found")
    if price is not None and mrp is not None and mrp < price:
        mrp = None
    return RefreshResult(
        current_price=price,
        mrp=mrp,
        discount_percent=calculate_discount_percent(price, mrp),
        stock_status=stock,  # type: ignore[arg-type]
        stock_reason=stock_reason,
        stock_confidence=stock_confidence,
        page_status="success",
        warnings=["verification_source:lightweight"],
    )


async def fetch_lightweight(platform: str, url: str, timeout_seconds: float = 8.0) -> RefreshResult:
    return await asyncio.to_thread(_fetch, platform, url, timeout_seconds)
