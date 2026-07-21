from __future__ import annotations

import argparse
import asyncio
import re
import urllib.parse
from typing import Any

from mayabu_common import utc_now
from mayabu_scraper_base import (
    BrowserSession,
    ScrapeConfig,
    attr_or_none,
    finalize_records,
    human_scroll,
    polite_sleep,
    recover_cards_when_empty,
    close_common_popups,
    discovery_health_report,
    extract_structural_discovery_records,
    save_or_print,
    text_or_none,
    wait_for_any_selector,
)

PLATFORM = "reliancedigital"
PAGE_SIZE = 12
CARD_SELECTORS = [
    "div.product-card",
    "[class*='product-card']",
    "[class*='productCard']",
    "li.product-item",
    "[class*='ProductCard']",
]
TITLE_SELECTORS = ["div.product-card-title", "[class*='product-title']", "[class*='productTitle']", "h3", "h2"]
PRICE_SELECTORS = ["div.price-container div.price", "[class*='selling-price']", "[class*='offer-price']", "[class*='new-price']", "[class*='sellingPrice']"]
MRP_SELECTORS = ["div.mrp-container div.mrp-amount", "[class*='mrp-amount']", "[class*='mrp']", "[class*='old-price']", "[class*='original-price']"]
DISCOUNT_SELECTORS = ["div.discount", "[class*='discount']", "[class*='savings']"]
LINK_SELECTORS = ["div.card-info-container a", "a[href*='/product/']", "a[href*='/p/']", "a[href]"]
IMAGE_SELECTORS = ["img.fy__img", "img[src*='jiostore']", "img[src*='cdn']", "img[src]"]


async def dismiss_overlays(page) -> None:
    try:
        await page.evaluate(
            """() => {
                ['#modal-wrapper','.modal-wrapper','.allow-access-modal','[class*="modal"]','[id*="modal"]'].forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => el.remove());
                });
            }"""
        )
    except Exception:
        pass


async def extract_card(card: Any) -> dict[str, Any] | None:
    title = await text_or_none(card, TITLE_SELECTORS)
    raw_link = await attr_or_none(card, LINK_SELECTORS, ["href"])
    link = raw_link or ""
    if link.startswith("/"):
        link = "https://www.reliancedigital.in" + link
    price = await text_or_none(card, PRICE_SELECTORS)
    mrp = await text_or_none(card, MRP_SELECTORS)
    discount = await text_or_none(card, DISCOUNT_SELECTORS)
    image = await attr_or_none(card, IMAGE_SELECTORS, ["src", "data-src"])
    if not title or not link:
        return None
    return {
        "title": title,
        "currentPrice": price or "N/A",
        "maxRetailPrice": mrp or "N/A",
        "discount": discount or None,
        "link": link,
        "image": image or "",
    }


async def detect_max_pages(page, fallback: int) -> int:
    try:
        spans = await page.query_selector_all("span[aria-label^='Goto page number']")
        numbers: list[int] = []
        for span in spans:
            label = await span.get_attribute("aria-label") or ""
            m = re.search(r"(\d+)$", label)
            if m:
                numbers.append(int(m.group(1)))
        if numbers:
            return max(numbers)
    except Exception:
        pass
    return fallback


async def scrape_reliancedigital(
    query: str,
    max_products: int | None = None,
    max_pages: int | None = 3,
    output: str | None = None,
    headless: bool = True,
    debug: bool = False,
) -> list[dict[str, Any]]:
    config = ScrapeConfig(query=query, max_products=max_products, max_pages=max_pages, output=output, headless=headless, debug=debug)
    observed_at = utc_now()
    raw_records: list[dict[str, Any]] = []

    async with BrowserSession(headless=headless, timeout_ms=config.timeout_ms) as session:
        page = await session.new_page()
        encoded = urllib.parse.quote_plus(query)
        requested_pages = max_pages or 1
        detected_pages = requested_pages
        actual_pages = requested_pages
        selector = None
        for page_no in range(1, requested_pages + 1):
            if page_no > actual_pages:
                break
            if max_products and len(raw_records) >= max_products:
                break
            url = f"https://www.reliancedigital.in/products?q={encoded}&page_no={page_no}&page_size={PAGE_SIZE}&page_type=number"
            print(f"[reliancedigital] page {page_no}: {url}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=config.timeout_ms)
            except Exception as exc:
                print(f"[reliancedigital] navigation failed on page {page_no}: {exc}")
                break
            await close_common_popups(page)
            await dismiss_overlays(page)
            if page_no == 1:
                selector = await wait_for_any_selector(page, CARD_SELECTORS, timeout_ms=20_000)
                detected_pages = await detect_max_pages(page, requested_pages)
                actual_pages = max(1, min(detected_pages, requested_pages))
                print(f"[reliancedigital] detected_pages={detected_pages}; actual_pages={actual_pages}; requested_pages={requested_pages}")
            if not selector:
                print("[reliancedigital] no product cards found; trying structural fallback")
                fallback = await extract_structural_discovery_records(page, PLATFORM, query, max_items=max_products or 120)
                if not fallback:
                    fallback = await recover_cards_when_empty(page, PLATFORM, query, config, reason="no_selector")
                raw_records.extend(fallback)
                if fallback:
                    print(f"[reliancedigital] structural/DOM fallback recovered {len(fallback)} raw cards")
                    continue
                print("[reliancedigital] no product cards found after fallback; stopping")
                break
            await human_scroll(page)
            cards = await page.query_selector_all(selector)
            page_added = 0
            for card in cards:
                item = await extract_card(card)
                if not item:
                    continue
                raw_records.append(item)
                page_added += 1
                if max_products and len(raw_records) >= max_products:
                    break
            print(f"[reliancedigital] page {page_no}: +{page_added} raw cards")
            if page_added == 0:
                fallback = await extract_structural_discovery_records(page, PLATFORM, query, max_items=max_products or 120)
                if not fallback:
                    fallback = await recover_cards_when_empty(page, PLATFORM, query, config, reason="zero_cards")
                raw_records.extend(fallback)
                if fallback:
                    print(f"[reliancedigital] structural/DOM fallback recovered {len(fallback)} raw cards")
                else:
                    break
            await polite_sleep(config)

    records = finalize_records(PLATFORM, query, raw_records, observed_at)
    health = discovery_health_report(records, min_products=min(10, max_products or 10))
    if debug:
        print(f"[reliancedigital] health: {health}")
    return await save_or_print(config, PLATFORM, records, observed_at)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mayabu Reliance Digital scraper")
    parser.add_argument("query")
    parser.add_argument("--max-products", type=int)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--output")
    parser.add_argument("--show-browser", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    asyncio.run(scrape_reliancedigital(args.query, args.max_products, args.max_pages, args.output, not args.show_browser, args.debug))


if __name__ == "__main__":
    main()
