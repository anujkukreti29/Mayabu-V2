"""Robust, reusable product-detail scraper registry.

The extractor prefers machine-readable JSON-LD/OpenGraph metadata and uses
platform selectors only as fallback. This is less brittle than depending on
obfuscated CSS class names.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from pathlib import Path
from typing import Any

from playwright.async_api import Page, async_playwright

from mayabu.core.config import get_app_settings
from mayabu_common import extract_native_id, extract_specs, normalize_url, parse_price
from mayabu.scrapers.platforms import detect_platform, validate_product_url
from mayabu.scrapers.detail.models import DetailProduct

logger = logging.getLogger(__name__)

_SELECTORS = {
    "amazon": {
        "title": ["#productTitle", "h1 span", "meta[property='og:title']"],
        "price": ["span.priceToPay span.a-offscreen", "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen", "meta[property='product:price:amount']"],
        "mrp": ["span.a-price.a-text-price span.a-offscreen", ".basisPrice .a-offscreen"],
        "image": ["#landingImage", "meta[property='og:image']"],
        "availability": ["#availability span", "#outOfStock"],
        "seller": ["#sellerProfileTriggerId", "#merchant-info"],
    },
    "flipkart": {
        "title": ["h1 span", "h1", "meta[property='og:title']"],
        "price": ["meta[property='product:price:amount']", "meta[itemprop='price']", "[itemprop='price']"],
        "mrp": ["meta[property='product:original_price:amount']"],
        "image": ["meta[property='og:image']", "img[loading='eager']"],
        "availability": ["[itemprop='availability']"],
        "seller": ["#sellerName", "[data-testid='seller-name']"],
    },
    "croma": {
        "title": ["h1", "meta[property='og:title']"],
        "price": ["meta[property='product:price:amount']", "[itemprop='price']"],
        "mrp": ["meta[property='product:original_price:amount']"],
        "image": ["meta[property='og:image']", "[itemprop='image']"],
        "availability": ["[itemprop='availability']"],
        "seller": [],
    },
    "reliancedigital": {
        "title": ["h1", "meta[property='og:title']"],
        "price": ["meta[property='product:price:amount']", "[itemprop='price']"],
        "mrp": ["meta[property='product:original_price:amount']"],
        "image": ["meta[property='og:image']", "[itemprop='image']"],
        "availability": ["[itemprop='availability']"],
        "seller": [],
    },
}

_USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
)


async def _text_or_attr(page: Page, selectors: list[str], attrs: tuple[str, ...] = ("content", "value", "src", "href")) -> str | None:
    for selector in selectors:
        try:
            element = await page.query_selector(selector)
            if not element:
                continue
            for attr in attrs:
                value = await element.get_attribute(attr)
                if value and value.strip():
                    return value.strip()
            value = (await element.inner_text()).strip()
            if value:
                return value
        except Exception:
            continue
    return None


def _flatten_jsonld(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(value, dict):
        out.append(value)
        graph = value.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                out.extend(_flatten_jsonld(item))
    elif isinstance(value, list):
        for item in value:
            out.extend(_flatten_jsonld(item))
    return out


async def _jsonld_product(page: Page) -> dict[str, Any]:
    scripts = await page.query_selector_all("script[type='application/ld+json']")
    candidates: list[dict[str, Any]] = []
    for script in scripts[:30]:
        try:
            raw = await script.text_content()
            if not raw:
                continue
            data = json.loads(raw.strip())
            candidates.extend(_flatten_jsonld(data))
        except Exception:
            continue
    for item in candidates:
        kind = item.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        if any(str(x).lower() == "product" for x in kinds if x):
            return item
    return {}


def _offer(product: dict[str, Any]) -> dict[str, Any]:
    offers = product.get("offers") or {}
    if isinstance(offers, list):
        for offer in offers:
            if isinstance(offer, dict):
                return offer
        return {}
    return offers if isinstance(offers, dict) else {}


def _image(product: dict[str, Any]) -> str | None:
    image = product.get("image")
    if isinstance(image, list):
        image = next((x for x in image if isinstance(x, str) and x), None)
    if isinstance(image, dict):
        image = image.get("url") or image.get("contentUrl")
    return str(image).strip() if image else None


def _numeric(value: Any) -> float | None:
    parsed = parse_price(value)
    return round(float(parsed), 2) if parsed is not None else None


def _availability(value: Any) -> str | None:
    text = str(value or "").lower()
    if "instock" in text or "in stock" in text:
        return "in_stock"
    if "outofstock" in text or "out of stock" in text:
        return "out_of_stock"
    if "preorder" in text or "coming" in text:
        return "coming_soon"
    return "unknown" if text else None


async def _save_artifacts(page: Page, platform: str, reason: str, artifact_dir: Path) -> dict[str, str]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-z0-9_-]+", "_", reason.lower())[:80]
    stem = f"{platform}_{safe}_{int(asyncio.get_running_loop().time() * 1000)}"
    screenshot = artifact_dir / f"{stem}.png"
    html = artifact_dir / f"{stem}.html"
    evidence: dict[str, str] = {}
    try:
        await page.screenshot(path=str(screenshot), full_page=True)
        evidence["screenshot_path"] = str(screenshot)
    except Exception:
        pass
    try:
        html.write_text(await page.content(), encoding="utf-8")
        evidence["html_path"] = str(html)
    except Exception:
        pass
    return evidence


async def _extract(page: Page, platform: str, url: str) -> DetailProduct:
    selectors = _SELECTORS[platform]
    jsonld = await _jsonld_product(page)
    offer = _offer(jsonld)

    title = jsonld.get("name") or await _text_or_attr(page, selectors["title"])
    current_price = _numeric(offer.get("price") or offer.get("lowPrice"))
    if current_price is None:
        current_price = _numeric(await _text_or_attr(page, selectors["price"]))
    price_specification = offer.get("priceSpecification") if isinstance(offer.get("priceSpecification"), dict) else {}
    mrp = _numeric(offer.get("highPrice") or price_specification.get("price") or price_specification.get("maxPrice"))
    if mrp is None:
        mrp = _numeric(await _text_or_attr(page, selectors["mrp"]))

    image_url = _image(jsonld) or await _text_or_attr(page, selectors["image"])
    availability = _availability(offer.get("availability") or await _text_or_attr(page, selectors["availability"]))
    seller = offer.get("seller") or jsonld.get("seller")
    if isinstance(seller, dict):
        seller = seller.get("name")
    seller_name = str(seller).strip() if seller else await _text_or_attr(page, selectors["seller"])

    aggregate = jsonld.get("aggregateRating") if isinstance(jsonld.get("aggregateRating"), dict) else {}
    rating = _numeric(aggregate.get("ratingValue"))
    review_count_value = aggregate.get("reviewCount") or aggregate.get("ratingCount")
    try:
        review_count = int(str(review_count_value).replace(",", "")) if review_count_value else None
    except ValueError:
        review_count = None

    canonical = await _text_or_attr(page, ["link[rel='canonical']"], attrs=("href",)) or normalize_url(url)
    canonical = normalize_url(canonical)
    native_id = extract_native_id(platform, canonical or url, jsonld.get("sku") or jsonld.get("mpn"))
    specs = extract_specs(str(title or ""), "laptop") if title else {}
    if jsonld.get("sku"):
        codes = set(specs.get("model_codes") or [])
        codes.add(str(jsonld["sku"]).upper())
        specs["model_codes"] = sorted(codes)

    warnings: list[str] = []
    if not title:
        warnings.append("missing_title")
    if current_price is None:
        warnings.append("missing_price")
    if mrp is not None and current_price is not None and mrp < current_price:
        warnings.append("mrp_below_price")
        mrp = None
    status = "success" if title and current_price is not None else ("partial" if title else "failed")

    return DetailProduct(
        platform=platform,
        url=url,
        canonical_url=canonical or normalize_url(url),
        title=str(title).strip() if title else None,
        native_id=native_id,
        current_price=current_price,
        mrp=mrp,
        currency=str(offer.get("priceCurrency") or "INR").upper(),
        image_url=image_url,
        availability=availability,
        seller_name=seller_name,
        rating=rating,
        review_count=review_count,
        specs=specs,
        status=status,
        warnings=warnings,
        evidence={"jsonld_found": bool(jsonld), "final_url": page.url},
    )


async def scrape_product_detail(
    url: str,
    *,
    platform: str | None = None,
    headless: bool = True,
    debug: bool = True,
    artifact_dir: str | Path = "artifacts/debug/detail",
) -> DetailProduct:
    settings = get_app_settings()
    platform = platform or detect_platform(url)
    canonical_input = validate_product_url(platform, url)
    last_error: Exception | None = None

    async with async_playwright() as playwright:
        for attempt in range(1, settings.scraper_navigation_attempts + 1):
            browser = None
            context = None
            page = None
            try:
                browser = await playwright.chromium.launch(headless=headless, args=["--no-sandbox", "--disable-dev-shm-usage"])
                context = await browser.new_context(
                    user_agent=random.choice(_USER_AGENTS),
                    viewport={"width": 1366, "height": 850},
                    locale="en-IN",
                    timezone_id="Asia/Kolkata",
                    extra_http_headers={"Accept-Language": "en-IN,en;q=0.9"},
                )
                page = await context.new_page()
                page.set_default_timeout(min(15000, settings.scraper_timeout_ms))
                response = await page.goto(canonical_input, wait_until="domcontentloaded", timeout=settings.scraper_timeout_ms)
                await page.wait_for_timeout(1600 + random.randint(0, 900))
                if response is not None and response.status == 404:
                    return DetailProduct(platform=platform, url=url, canonical_url=canonical_input, status="not_found", warnings=["http_404"])
                if detect_platform(page.url) != platform:
                    raise ValueError(f"Unexpected cross-platform redirect to {page.url}")
                html = (await page.content()).lower()
                blocked_terms = ("captcha", "robot check", "unusual traffic", "access denied", "verify you are human")
                if any(term in html for term in blocked_terms):
                    result = DetailProduct(platform=platform, url=url, canonical_url=canonical_input, status="blocked", warnings=["blocked_or_captcha"])
                    if debug:
                        result.evidence.update(await _save_artifacts(page, platform, "blocked", Path(artifact_dir)))
                    return result
                result = await _extract(page, platform, canonical_input)
                if debug and result.status != "success":
                    result.evidence.update(await _save_artifacts(page, platform, result.status, Path(artifact_dir)))
                return result
            except Exception as exc:
                last_error = exc
                logger.warning("detail_scrape_attempt_failed", extra={"platform": platform, "attempt": attempt, "error": str(exc)[:500]})
                if page is not None and debug and attempt == settings.scraper_navigation_attempts:
                    evidence = await _save_artifacts(page, platform, "error", Path(artifact_dir))
                else:
                    evidence = {}
                if attempt < settings.scraper_navigation_attempts:
                    await asyncio.sleep(settings.scraper_retry_base_seconds * (2 ** (attempt - 1)) + random.random())
                else:
                    return DetailProduct(
                        platform=platform,
                        url=url,
                        canonical_url=canonical_input,
                        status="failed",
                        warnings=[f"detail_scrape_error: {str(exc)[:500]}"],
                        evidence=evidence,
                    )
            finally:
                if context is not None:
                    await context.close()
                if browser is not None:
                    await browser.close()

    raise RuntimeError(str(last_error or "detail scrape failed"))
