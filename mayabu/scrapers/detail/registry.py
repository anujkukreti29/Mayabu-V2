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
from mayabu.domain.categories.registry import detect_category_from_evidence
from mayabu_common import extract_native_id, extract_specs, normalize_url, parse_price
from mayabu.scrapers.platforms import detect_platform, validate_product_url
from mayabu.scrapers.detail.models import DetailProduct

logger = logging.getLogger(__name__)

_DEFAULT_SELECTORS = {
    "title": ["h1", "meta[property='og:title']", "[itemprop='name']"],
    "price": ["meta[property='product:price:amount']", "[itemprop='price']"],
    "mrp": ["meta[property='product:original_price:amount']"],
    "image": ["meta[property='og:image']", "[itemprop='image']"],
    "availability": ["[itemprop='availability']"],
    "seller": [],
}

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
    "croma": dict(_DEFAULT_SELECTORS),
    "reliancedigital": dict(_DEFAULT_SELECTORS),
    "vijaysales": dict(_DEFAULT_SELECTORS),
    "jiomart": dict(_DEFAULT_SELECTORS),
    "poorvika": dict(_DEFAULT_SELECTORS),
    "bajajelectronics": dict(_DEFAULT_SELECTORS),
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
    images = _images(product)
    return images[0] if images else None


def _images(product: dict[str, Any]) -> list[str]:
    """Extract ordered gallery URLs from JSON-LD Product.image."""
    out: list[str] = []
    seen: set[str] = set()

    def _add(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                _add(item)
            return
        if isinstance(value, dict):
            value = value.get("url") or value.get("contentUrl") or value.get("@id")
        text = str(value or "").strip()
        if not text or text.startswith("data:") or text in seen:
            return
        low = text.lower()
        if any(tok in low for tok in ("1x1", "pixel", "spacer", "logo", "badge", "sprite", "tracking")):
            return
        seen.add(text)
        out.append(text)

    _add(product.get("image"))
    return out[:10]


_GALLERY_SELECTORS: dict[str, list[str]] = {
    "amazon": [
        "#altImages img",
        "#imageBlock_feature_div img",
        "#landingImage",
    ],
    "flipkart": [
        "ul[class*='_3GnUWp'] img",
        "div[class*='_2E1Fgs'] img",
        "img[loading='eager']",
    ],
    "croma": [
        "[class*='pdp-gallery'] img",
        "[class*='product-gallery'] img",
        "meta[property='og:image']",
    ],
    "reliancedigital": [
        "[class*='pdp'] img",
        "[class*='gallery'] img",
        "meta[property='og:image']",
    ],
    "vijaysales": ["[class*='gallery'] img", "meta[property='og:image']"],
    "poorvika": ["[class*='gallery'] img", "meta[property='og:image']"],
}


async def _gallery_from_dom(page: Page, platform: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for selector in _GALLERY_SELECTORS.get(platform, ["meta[property='og:image']"]):
        try:
            elements = await page.query_selector_all(selector)
        except Exception:
            continue
        for el in elements[:24]:
            try:
                raw = (
                    await el.get_attribute("data-old-hires")
                    or await el.get_attribute("data-a-dynamic-image")
                    or await el.get_attribute("srcset")
                    or await el.get_attribute("data-src")
                    or await el.get_attribute("content")
                    or await el.get_attribute("src")
                )
            except Exception:
                continue
            if not raw:
                continue
            # Amazon data-a-dynamic-image is JSON map of url->size
            if raw.strip().startswith("{"):
                try:
                    payload = json.loads(raw)
                    if isinstance(payload, dict):
                        # Prefer largest listed dimension
                        ranked = sorted(
                            ((str(u), int(sz[0]) * int(sz[1]) if isinstance(sz, list) and len(sz) >= 2 else 0)
                             for u, sz in payload.items()),
                            key=lambda item: item[1],
                            reverse=True,
                        )
                        for url, _ in ranked[:6]:
                            if url and url not in seen:
                                seen.add(url)
                                urls.append(url)
                        continue
                except Exception:
                    pass
            # srcset: take last (usually largest)
            if "," in raw and " " in raw:
                parts = [p.strip().split(" ")[0] for p in raw.split(",") if p.strip()]
                raw = parts[-1] if parts else raw
            value = str(raw).strip()
            if not value or value.startswith("data:") or value in seen:
                continue
            low = value.lower()
            if any(tok in low for tok in ("1x1", "pixel", "spacer", "logo", "badge", "sprite", "icon", "tracking")):
                continue
            # Skip tiny thumbs by filename heuristics
            if re.search(r"[_-](ss|sx|sy)\d{2,3}\.", low):
                continue
            seen.add(value)
            urls.append(value)
            if len(urls) >= 10:
                return urls
    return urls


def _numeric(value: Any) -> float | None:
    parsed = parse_price(value)
    return round(float(parsed), 2) if parsed is not None else None


async def _amazon_variant_identity(page: Page) -> dict[str, str]:
    """Factual Amazon selected-variant text (color / size / configuration).

    Prefers selected twister labels and variation rows. Does not infer from images.
    """
    out: dict[str, str] = {}
    selectors = [
        ("color", "#variation_color_name .selection"),
        ("color", "#inline-twister-expanded-dimension-text-color_name"),
        ("color", "#variation_color_name span.selection"),
        ("size", "#variation_size_name .selection"),
        ("size", "#inline-twister-expanded-dimension-text-size_name"),
        ("style", "#variation_style_name .selection"),
        ("configuration", "#variation_configuration_name .selection"),
        ("configuration", "#inline-twister-expanded-dimension-text-configuration"),
    ]
    for key, selector in selectors:
        if key in out:
            continue
        try:
            el = await page.query_selector(selector)
            if not el:
                continue
            text = ((await el.inner_text()) or "").strip()
            if text and len(text) < 80:
                out[key] = text
        except Exception:
            continue
    # Selected twister row aria labels often include "Color: Midnight"
    try:
        selected = await page.query_selector(
            "#twister .swatchSelect[aria-checked='true'], "
            "#twister .swatchSelect.selected, "
            "#inline-twister-row .a-button-selected"
        )
        if selected:
            label = (
                (await selected.get_attribute("aria-label"))
                or (await selected.get_attribute("title"))
                or ""
            ).strip()
            if label and "color" not in out and re.search(r"color", label, re.I):
                out["color"] = re.sub(r"(?i)^.*?color\s*[:\-]\s*", "", label).strip()[:80]
    except Exception:
        pass
    return out


async def _amazon_selling_price(page: Page) -> tuple[float | None, float | None]:
    """Extract Amazon India current selling price + MRP from the buybox only.

    Prefer selected offer / priceToPay. Never treat EMI, bank offer, or
    recommendation carousel prices as the selling price.
    """
    selling: float | None = None
    mrp: float | None = None

    # Scoped to the buybox / core price feature — not related products.
    selling_selectors = [
        "#corePrice_feature_div span.priceToPay span.a-offscreen",
        "#corePriceDisplay_desktop_feature_div span.priceToPay span.a-offscreen",
        "#corePriceDisplay_desktop_feature_div .a-price.priceToPay .a-offscreen",
        "#apex_desktop span.priceToPay span.a-offscreen",
        "#tp_price_block_total_price_ww span.a-offscreen",
        "#priceblock_dealprice",
        "#priceblock_ourprice",
        "#corePrice_feature_div .a-price[data-a-color='price'] .a-offscreen",
        "#corePriceDisplay_desktop_feature_div .a-price[data-a-color='price'] .a-offscreen",
    ]
    for selector in selling_selectors:
        try:
            el = await page.query_selector(selector)
            if not el:
                continue
            raw = (await el.inner_text() or "").strip()
            if not raw:
                raw = (
                    (await el.get_attribute("content") or "")
                    or (await el.get_attribute("value") or "")
                ).strip()
            price = _numeric(raw)
            if price is not None and price > 0:
                selling = price
                break
        except Exception:
            continue

    # Whole + fraction fallback when a-offscreen is empty / stripped.
    if selling is None:
        whole_selectors = [
            "#corePrice_feature_div span.priceToPay span.a-price-whole",
            "#corePriceDisplay_desktop_feature_div span.priceToPay span.a-price-whole",
            "#corePriceDisplay_desktop_feature_div .a-price[data-a-color='price'] span.a-price-whole",
            "#apex_desktop span.a-price-whole",
        ]
        for selector in whole_selectors:
            try:
                whole_el = await page.query_selector(selector)
                if not whole_el:
                    continue
                whole = (await whole_el.inner_text() or "").strip()
                frac = ""
                try:
                    frac_el = await page.query_selector(
                        selector.replace("a-price-whole", "a-price-fraction")
                    )
                    if frac_el:
                        frac = (await frac_el.inner_text() or "").strip()
                except Exception:
                    frac = ""
                combined = f"{whole}.{frac}" if frac else whole
                price = _numeric(combined)
                if price is not None and price > 0:
                    selling = price
                    break
            except Exception:
                continue

    mrp_selectors = [
        "#corePriceDisplay_desktop_feature_div .basisPrice .a-offscreen",
        "#corePrice_feature_div .a-text-price .a-offscreen",
        "#corePriceDisplay_desktop_feature_div span.a-price.a-text-price span.a-offscreen",
        "span.a-price.a-text-price.apex-basisprice-value span.a-offscreen",
    ]
    for selector in mrp_selectors:
        try:
            el = await page.query_selector(selector)
            if not el:
                continue
            price = _numeric((await el.inner_text() or "").strip())
            if price is not None and price > 0:
                mrp = price
                break
        except Exception:
            continue

    # If we only found one price and it came from a strike-through/basis slot, keep as MRP.
    if selling is not None and mrp is not None and selling >= mrp:
        # Mis-assigned: basis often parsed as sell — keep lower as sell only if clearly deal.
        if selling == mrp:
            pass
        else:
            # Selling should never exceed MRP; swap if inverted.
            selling, mrp = mrp, selling

    return selling, mrp


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
    selectors = _SELECTORS.get(platform) or _DEFAULT_SELECTORS
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

    # Amazon India: JSON-LD often exposes list/MRP but omits the selected buybox deal price.
    if platform == "amazon":
        amz_sell, amz_mrp = await _amazon_selling_price(page)
        if amz_sell is not None:
            current_price = amz_sell
        if amz_mrp is not None and (mrp is None or mrp < amz_sell):
            mrp = amz_mrp
        # Never promote JSON-LD highPrice alone as current selling price.
        if current_price is None and mrp is not None:
            # Keep MRP separate; leave current_price missing rather than inventing sell=MRP.
            pass

    image_url = _image(jsonld) or await _text_or_attr(page, selectors["image"])
    if image_url:
        low = image_url.lower()
        if any(tok in low for tok in ("1x1", "pixel", "spacer", "logo", "badge", "sprite", "tracking", "vs-logo")):
            image_url = None
    gallery = _images(jsonld)
    dom_gallery = await _gallery_from_dom(page, platform)
    for gurl in dom_gallery:
        if gurl not in gallery:
            gallery.append(gurl)
    gallery = [
        g
        for g in gallery
        if not any(
            tok in g.lower()
            for tok in ("1x1", "pixel", "spacer", "logo", "badge", "sprite", "tracking", "vs-logo")
        )
    ]
    if image_url and image_url not in gallery:
        gallery = [image_url, *gallery]
    gallery = gallery[:10]
    if not image_url and gallery:
        image_url = gallery[0]
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
    breadcrumb = ""
    try:
        crumbs = await page.query_selector_all("[itemtype*='BreadcrumbList'] [itemprop='name'], nav[aria-label*='breadcrumb'] a")
        parts: list[str] = []
        for crumb in crumbs[:8]:
            text = (await crumb.inner_text()).strip()
            if text:
                parts.append(text)
        breadcrumb = " > ".join(parts)
    except Exception:
        breadcrumb = ""
    structured_category = ""
    category_value = jsonld.get("category")
    if isinstance(category_value, str):
        structured_category = category_value
    elif isinstance(category_value, list):
        structured_category = " ".join(str(v) for v in category_value)
    detected = detect_category_from_evidence(
        title=str(title or ""),
        breadcrumbs=breadcrumb,
        url=canonical or url,
        structured_category=structured_category,
    )
    # CRITICAL: never coerce unknown/accessory into laptop.
    specs = extract_specs(str(title or ""), detected) if title else {"category": detected}
    if platform == "amazon":
        variant = await _amazon_variant_identity(page)
        # Re-extract with selected variant text when title alone lacks color/config.
        variant_blob = " ".join(
            v for k, v in variant.items() if k in {"color", "size", "style", "configuration"} and v
        )
        if variant_blob and title and detected not in {"unknown", "accessory"}:
            enriched = extract_specs(f"{title} {variant_blob}", detected)
            for key in ("color", "ram_gb", "storage_gb", "model_codes", "cpu_models", "cpu_series"):
                if enriched.get(key) and not specs.get(key):
                    specs[key] = enriched[key]
        if variant.get("color") and not specs.get("color"):
            from mayabu.search.public_offers import extract_color_token

            token = extract_color_token(variant["color"]) or variant["color"].strip().lower()
            if token:
                specs["color"] = token
        color_json = jsonld.get("color")
        if color_json and not specs.get("color"):
            from mayabu.search.public_offers import extract_color_token

            token = extract_color_token(str(color_json)) or str(color_json).strip().lower()
            if token:
                specs["color"] = token
        if variant:
            specs["amazon_variant"] = variant
    if jsonld.get("sku") and detected not in {"unknown", "accessory"}:
        codes = set(specs.get("model_codes") or [])
        codes.add(str(jsonld["sku"]).upper())
        specs["model_codes"] = sorted(codes)
    if jsonld.get("mpn") and detected not in {"unknown", "accessory"}:
        codes = set(specs.get("model_codes") or [])
        codes.add(str(jsonld["mpn"]).upper())
        specs["model_codes"] = sorted(codes)
    if jsonld.get("brand"):
        brand = jsonld["brand"]
        if isinstance(brand, dict):
            brand = brand.get("name")
        if brand and not specs.get("brand"):
            specs["brand"] = str(brand).strip()
    if detected in {"unknown", "accessory"}:
        warnings_pre = ["category_unknown" if detected == "unknown" else "category_accessory"]
    else:
        warnings_pre = []

    warnings: list[str] = list(warnings_pre)
    if not title:
        warnings.append("missing_title")
    if current_price is None:
        warnings.append("missing_price")
    if mrp is not None and current_price is not None and mrp < current_price:
        warnings.append("mrp_below_price")
        mrp = None
    status = "success" if title and current_price is not None else ("partial" if title else "failed")

    highlights: list[str] = []
    try:
        for sel in ("#feature-bullets li span", "[data-testid='product-highlights'] li", ".product-highlights li"):
            els = await page.query_selector_all(sel)
            for el in els[:12]:
                text = ((await el.inner_text()) or "").strip()
                if text and len(text) < 240 and text.lower() not in {h.lower() for h in highlights}:
                    highlights.append(text)
            if highlights:
                break
    except Exception:
        highlights = []

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
        image_urls=gallery,
        availability=availability,
        seller_name=seller_name,
        rating=rating,
        review_count=review_count,
        specs=specs,
        highlights=highlights[:12],
        status=status,
        warnings=warnings,
        evidence={
            "jsonld_found": bool(jsonld),
            "final_url": page.url,
            "detected_category": detected,
            "gallery_count": len(gallery),
        },
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
