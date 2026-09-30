"""Shared lightweight retail discovery helpers for new platforms.

Platform modules remain one-scraper-per-retailer. Pure HTML parsing lives in
retail_parse.py so unit tests do not require Playwright.
"""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any, Callable

from playwright.async_api import Page

logger = logging.getLogger(__name__)

from mayabu.platforms.registry import get_platform
from mayabu.scrapers.retail_parse import (
    abs_url,
    extract_jsonld_products,
    html_looks_blocked,
    jsonld_to_raw_record,
    price_to_int,
)
from mayabu_common import utc_now
from mayabu_scraper_base import (
    BrowserSession,
    ScrapeConfig,
    close_common_popups,
    discovery_health_report,
    extract_structural_discovery_records,
    finalize_records,
    human_scroll,
    polite_sleep,
    recover_cards_when_empty,
    save_or_print,
    wait_for_any_selector,
)


class DiscoveryResult(list):
    """List of discovery records with scrape-level status metadata."""

    scrape_status: str
    blocked: bool
    health: dict[str, Any]

    def __init__(self, records: list[dict[str, Any]] | None = None, *, scrape_status: str = "success"):
        super().__init__(records or [])
        self.scrape_status = scrape_status
        self.blocked = scrape_status == "blocked"
        self.health = {}

GENERIC_CARD_SELECTORS = [
    "[data-testid*='product']",
    "[itemtype*='Product']",
    "li.product-item",
    "div.product-item",
    "[class*='product-card']",
    "[class*='productCard']",
    "[class*='product-item']",
    "[class*='ProductCard']",
    "article[class*='product']",
    "li[class*='product']",
    "div[class*='product']",
]

GENERIC_TITLE_SELECTORS = [
    "h2",
    "h3",
    "h4",
    "[itemprop='name']",
    "[class*='product-title']",
    "[class*='productTitle']",
    "[class*='title']",
    "a[title]",
]

GENERIC_PRICE_SELECTORS = [
    "[itemprop='price']",
    "[data-testid*='price']",
    "[class*='selling-price']",
    "[class*='sellingPrice']",
    "[class*='offer-price']",
    "[class*='offerPrice']",
    "[class*='new-price']",
    "[class*='final-price']",
    "[class*='finalPrice']",
    "[class*='discounted-price']",
    "[class*='our-price']",
    # Generic price last — may include EMI; price_to_int rejects EMI noise.
    "[class*='price']:not([class*='emi']):not([class*='month'])",
]

GENERIC_MRP_SELECTORS = [
    "[class*='mrp']",
    "[class*='old-price']",
    "[class*='original-price']",
    "[class*='strike']",
    "[class*='list-price']",
]

GENERIC_IMAGE_SELECTORS = [
    "img[src]",
    "img[data-src]",
    "img[data-lazy-src]",
    "source[srcset]",
]


def build_search_url(platform: str, query: str, page: int = 1) -> str:
    info = get_platform(platform)
    if info is None:
        raise ValueError(f"Unknown platform: {platform}")
    encoded = urllib.parse.quote(query.strip())
    encoded_plus = urllib.parse.quote_plus(query.strip())
    template = info.search_path_template
    path = template.format(query=encoded, page=page, query_plus=encoded_plus)
    if "{query}" not in template and "q=" in template:
        path = template.format(query=encoded_plus, page=page)
    if page > 1 and "page=" not in path and "?" in path:
        path = f"{path}&page={page}"
    elif page > 1 and "page=" not in path and "{page}" not in template:
        sep = "&" if "?" in path else "?"
        path = f"{path}{sep}page={page}"
    return info.base_url.rstrip("/") + path


async def page_looks_blocked(page: Page) -> bool:
    try:
        html = await page.content()
    except Exception as exc:
        logger.debug("page_content_unavailable", extra={"error": type(exc).__name__})
        return False
    title = ""
    try:
        title = await page.title()
    except Exception as exc:
        logger.debug("page_title_unavailable", extra={"error": type(exc).__name__})
    return html_looks_blocked(html, title)


async def text_first(card: Any, selectors: list[str]) -> str | None:
    for selector in selectors:
        try:
            el = await card.query_selector(selector)
            if not el:
                continue
            for attr in ("content", "value", "title", "aria-label"):
                value = await el.get_attribute(attr)
                if value and value.strip():
                    return value.strip()
            text = (await el.inner_text()).strip()
            if text:
                return text
        except Exception:
            continue
    return None


async def selling_price_text(card: Any, selectors: list[str]) -> str | None:
    """Return the first price-like text that parses as a selling price (not EMI-only)."""
    candidates: list[str] = []
    for selector in selectors:
        try:
            els = await card.query_selector_all(selector)
        except Exception:
            continue
        for el in els:
            try:
                for attr in ("content", "value", "title", "aria-label"):
                    value = await el.get_attribute(attr)
                    if value and value.strip():
                        candidates.append(value.strip())
                text = (await el.inner_text()).strip()
                if text:
                    candidates.append(text)
            except Exception:
                continue
    for text in candidates:
        if price_to_int(text) is not None:
            return text.split("\n")[0].strip()
    return candidates[0] if candidates else None


async def attr_first(card: Any, selectors: list[str], attrs: list[str]) -> str | None:
    for selector in selectors:
        try:
            el = await card.query_selector(selector)
            if not el:
                continue
            for attr in attrs:
                value = await el.get_attribute(attr)
                if value and value.strip():
                    return value.strip()
        except Exception:
            continue
    return None


async def extract_from_product_links(
    page: Page,
    *,
    base_url: str,
    link_substring: str,
    max_items: int = 80,
) -> list[dict[str, Any]]:
    """Fallback: discover cards via product href patterns, then climb to a card root."""
    anchors = await page.query_selector_all(f"a[href*='{link_substring}']")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for anchor in anchors:
        try:
            href = await anchor.get_attribute("href")
            link = abs_url(base_url, href)
            if not link or link in seen:
                continue
            title = (await anchor.get_attribute("title") or "").strip()
            if not title:
                title = ((await anchor.inner_text()) or "").strip()
            # Climb to a likely card container for price/image.
            card = await anchor.evaluate_handle(
                """el => {
                  let node = el;
                  for (let i = 0; i < 6 && node; i++) {
                    node = node.parentElement;
                    if (!node) break;
                    const cls = (node.className || '').toString().toLowerCase();
                    if (cls.includes('product') || cls.includes('card') || node.tagName === 'LI' || node.tagName === 'ARTICLE') {
                      return node;
                    }
                  }
                  return el.parentElement || el;
                }"""
            )
            price_text = await selling_price_text(card, GENERIC_PRICE_SELECTORS)
            mrp_text = await text_first(card, GENERIC_MRP_SELECTORS)
            image = await attr_first(
                card,
                GENERIC_IMAGE_SELECTORS,
                ["src", "data-src", "data-lazy-src", "srcset"],
            )
            if image and "," in image and " " in image:
                image = image.split(",")[0].strip().split(" ")[0]
            if not title:
                # Try heading inside card
                title = (await text_first(card, GENERIC_TITLE_SELECTORS)) or ""
            if not title or len(title) < 5:
                continue
            seen.add(link)
            out.append(
                {
                    "title": title.split("\n")[0].strip()[:300],
                    "currentPrice": price_text or "N/A",
                    "maxRetailPrice": mrp_text or "N/A",
                    "discount": None,
                    "link": link,
                    "image": abs_url(base_url, image) if image else "",
                }
            )
            if len(out) >= max_items:
                break
        except Exception:
            continue
    return out


async def extract_generic_card(
    card: Any,
    *,
    base_url: str,
    link_substring: str,
) -> dict[str, Any] | None:
    title = await text_first(card, GENERIC_TITLE_SELECTORS)
    href = None
    for selector in (f"a[href*='{link_substring}']", "a[href]"):
        try:
            el = await card.query_selector(selector)
            if el:
                href = await el.get_attribute("href")
                if href:
                    break
        except Exception:
            continue
    link = abs_url(base_url, href)
    if not title or not link:
        return None
    title_clean = title.split("\n")[0].strip()[:300]
    title_l = title_clean.lower()
    if title_l in {"filter by", "sort by"} or title_l.startswith("sort by "):
        return None
    if "search?" in link and "/p/" not in link:
        return None
    price_text = await selling_price_text(card, GENERIC_PRICE_SELECTORS)
    mrp_text = await text_first(card, GENERIC_MRP_SELECTORS)
    image = await attr_first(
        card,
        GENERIC_IMAGE_SELECTORS,
        ["src", "data-src", "data-lazy-src", "srcset"],
    )
    if image and "," in image and " " in image:
        image = image.split(",")[0].strip().split(" ")[0]
    return {
        "title": title_clean,
        "currentPrice": price_text or "N/A",
        "maxRetailPrice": mrp_text or "N/A",
        "discount": None,
        "link": link,
        "image": abs_url(base_url, image) if image else "",
    }


async def scrape_retail_discovery(
    platform: str,
    query: str,
    *,
    max_products: int | None = None,
    max_pages: int | None = 3,
    output: str | None = None,
    headless: bool = True,
    debug: bool = False,
    link_substring: str = "/p/",
    card_selectors: list[str] | None = None,
    build_url: Callable[[str, int], str] | None = None,
    parse_embedded: Callable[[str], list[dict[str, Any]]] | None = None,
    start_page: int = 1,
) -> list[dict[str, Any]]:
    """Generic bounded discovery loop used by new retail platforms."""
    info = get_platform(platform)
    if info is None:
        raise ValueError(f"Unsupported platform: {platform}")
    config = ScrapeConfig(
        query=query,
        max_products=max_products,
        max_pages=max_pages,
        output=output,
        headless=headless,
        debug=debug,
    )
    observed_at = utc_now()
    raw_records: list[dict[str, Any]] = []
    scrape_status = "success"
    url_builder = build_url or (lambda q, page: build_search_url(platform, q, page))
    selectors = card_selectors or GENERIC_CARD_SELECTORS

    async with BrowserSession(headless=headless, timeout_ms=config.timeout_ms) as session:
        page = await session.new_page()
        total_pages = max(1, max_pages or 1)
        first_page = max(1, int(start_page or 1))
        for page_no in range(first_page, first_page + total_pages):
            if max_products and len(raw_records) >= max_products:
                break
            url = url_builder(query, page_no)
            print(f"[{platform}] page {page_no}: {url}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=config.timeout_ms)
            except Exception as exc:
                print(f"[{platform}] navigation failed on page {page_no}: {exc}")
                scrape_status = "failed"
                break
            await close_common_popups(page)
            if await page_looks_blocked(page):
                print(f"[{platform}] blocked/captcha detected; stopping")
                scrape_status = "blocked"
                break

            html = await page.content()
            if parse_embedded:
                embedded = parse_embedded(html)
                usable_embedded = [
                    item
                    for item in embedded
                    if item
                    and str(item.get("title") or "").strip()
                    and str(item.get("link") or "").strip()
                    and len(str(item.get("title") or "").strip()) >= 8
                ]
                for item in usable_embedded:
                    raw_records.append(item)
                    if max_products and len(raw_records) >= max_products:
                        break
                if usable_embedded:
                    print(f"[{platform}] page {page_no}: +{len(usable_embedded)} embedded records")
                    await polite_sleep(config)
                    continue

            jsonld_items = extract_jsonld_products(html)
            added_jsonld = 0
            for product in jsonld_items:
                item = jsonld_to_raw_record(product, base_url=info.base_url)
                if not item or not item.get("link"):
                    continue
                raw_records.append(item)
                added_jsonld += 1
                if max_products and len(raw_records) >= max_products:
                    break
            if added_jsonld:
                print(f"[{platform}] page {page_no}: +{added_jsonld} json-ld products")
                await polite_sleep(config)
                continue

            selector = await wait_for_any_selector(page, selectors, timeout_ms=15_000)
            if not selector:
                fallback = await extract_structural_discovery_records(
                    page, platform, query, max_items=max_products or 120
                )
                if not fallback:
                    fallback = await recover_cards_when_empty(
                        page, platform, query, config, reason="no_selector"
                    )
                raw_records.extend(fallback)
                if not fallback:
                    print(f"[{platform}] no product cards found; stopping")
                    break
                await polite_sleep(config)
                continue

            await human_scroll(page)
            cards = await page.query_selector_all(selector)
            page_added = 0
            for card in cards:
                item = await extract_generic_card(
                    card, base_url=info.base_url, link_substring=link_substring
                )
                if not item:
                    continue
                raw_records.append(item)
                page_added += 1
                if max_products and len(raw_records) >= max_products:
                    break
            print(f"[{platform}] page {page_no}: +{page_added} raw cards")
            # Prefer link-based extraction when card selectors matched chrome or
            # returned too few priced products (common on Vijay Sales PLPs).
            if page_added == 0 or page_added < min(8, max_products or 8):
                link_fallback = await extract_from_product_links(
                    page,
                    base_url=info.base_url,
                    link_substring=link_substring,
                    max_items=max_products or 80,
                )
                if link_fallback:
                    raw_records.extend(link_fallback)
                    print(f"[{platform}] page {page_no}: +{len(link_fallback)} link-fallback cards")
                elif page_added == 0:
                    fallback = await extract_structural_discovery_records(
                        page, platform, query, max_items=max_products or 120
                    )
                    raw_records.extend(fallback)
                    if not fallback:
                        break
            await polite_sleep(config)

    seen: dict[str, dict[str, Any]] = {}
    for item in raw_records:
        link = str(item.get("link") or "")
        if not link:
            continue
        existing = seen.get(link)
        if existing is None:
            seen[link] = item
            continue
        # Prefer the record with a parseable selling price / image.
        if price_to_int(existing.get("currentPrice")) is None and price_to_int(item.get("currentPrice")) is not None:
            seen[link] = item
        elif not existing.get("image") and item.get("image"):
            seen[link] = item
    deduped = list(seen.values())
    if max_products:
        deduped = deduped[:max_products]

    records = finalize_records(platform, query, deduped, observed_at)
    if scrape_status == "success" and not records:
        scrape_status = "empty"
    health = discovery_health_report(
        records,
        min_products=min(10, max_products or 10),
        scrape_status=scrape_status,
    )
    if debug:
        print(f"[{platform}] health: {health}")
    saved = await save_or_print(config, platform, records, observed_at)
    result = DiscoveryResult(saved, scrape_status=scrape_status)
    result.health = health
    return result


# Re-exports for callers that historically imported parsers from this module.
__all__ = [
    "abs_url",
    "build_search_url",
    "extract_jsonld_products",
    "jsonld_to_raw_record",
    "page_looks_blocked",
    "price_to_int",
    "scrape_retail_discovery",
]
